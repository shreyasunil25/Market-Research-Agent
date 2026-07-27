import os
import sqlite3
from typing import TypedDict, Optional

from langchain_ollama import ChatOllama
from tavily import TavilyClient
from langgraph.graph import StateGraph, START, END

llm = ChatOllama(model="llama3.2", temperature=0)
# tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
tavily_key= os.environ.get("TAVILY_API_KEY")
tavily= TavilyClient(api_key=tavily_key)

class State(TypedDict):
    industry: str
    research_findings: Optional[str]
    sql_metrics: Optional[str]
    report: Optional[str]
    next_step: str
    loop_count: int


def researcher_node(state: State) -> dict:
    print("→ researcher running")
    try:
        response = tavily.search(
            query=f"{state['industry']} market trends news 2026",
            max_results=5,
            search_depth="basic",
            include_answer=True,
        )
        snippets = "\n\n".join(f"- {r['title']}: {r['content']}" for r in response["results"])
    except Exception as e:
        return {"research_findings": f"Web research unavailable ({e})"}

    prompt = f"Summarize these into 3-4 concise bullet points on {state['industry']}:\n\n{snippets}"
    summary = llm.invoke(prompt).content
    return {"research_findings": summary}

# def sql_analyst_node(state: State) -> dict:
#     print("→ sql_analyst running")
#     try:
#         conn = sqlite3.connect("market.db")   # rename to your actual db filename
#         industry = state["industry"]

#         latest_year = conn.execute(
#             "SELECT MAX(year) FROM sales WHERE category LIKE ?", (f"%{industry}%",)
#         ).fetchone()[0]

#         if latest_year is None:
#             conn.close()
#             return {"sql_metrics": f"No data found for category matching '{industry}'"}

#         top_companies = conn.execute("""
#             SELECT company, SUM(units_sold) AS total_units, SUM(revenue) AS total_revenue
#             FROM sales
#             WHERE category LIKE ? AND year = ?
#             GROUP BY company
#             ORDER BY total_revenue DESC
#             LIMIT 5
#         """, (f"%{industry}%", latest_year)).fetchall()

#         totals = conn.execute("""
#             SELECT SUM(revenue), SUM(profit), AVG(unit_price), AVG(customer_rating)
#             FROM sales
#             WHERE category LIKE ? AND year = ?
#         """, (f"%{industry}%", latest_year)).fetchone()

#         total_revenue, total_profit, avg_price, avg_rating = totals

#         yoy = conn.execute("""
#             SELECT year, SUM(revenue)
#             FROM sales
#             WHERE category LIKE ?
#             GROUP BY year
#             ORDER BY year
#         """, (f"%{industry}%",)).fetchall()

#         conn.close()

#         metrics = (
#             f"Latest year: {latest_year}\n"
#             f"Top companies by revenue: {top_companies}\n"
#             f"Total revenue: {total_revenue:,.0f}\n"
#             f"Total profit: {total_profit:,.0f}\n"
#             f"Average unit price: {avg_price:.2f}\n"
#             f"Average customer rating: {avg_rating:.2f}\n"
#             f"Revenue by year: {yoy}"
#         )
#     except Exception as e:
#         print(f"   ⚠️ SQL query failed: {e}")
#         raise

#     return {"sql_metrics": metrics}


import sqlite3

def find_matching_table(conn, industry: str) -> str | None:
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    key = industry.lower().replace(" ", "_")
    for table in tables:
        if key in table.lower() or table.lower().replace("_sales", "") in key:
            return table
    return None


def sql_analyst_node(state: State) -> dict:
    print("→ sql_analyst running")
    try:
        conn = sqlite3.connect("market_data.db")
        table = find_matching_table(conn, state["industry"])

        if table is None:
            conn.close()
            return {"sql_metrics": f"No matching table found for '{state['industry']}'"}

        # table name comes from sqlite_master (our own db), not raw user input — safe to interpolate
        latest_year = conn.execute(f"SELECT MAX(year) FROM {table}").fetchone()[0]

        top_companies = conn.execute(f"""
            SELECT company, SUM(units_sold) AS total_units, SUM(revenue) AS total_revenue
            FROM {table}
            WHERE year = ?
            GROUP BY company
            ORDER BY total_revenue DESC
            LIMIT 5
        """, (latest_year,)).fetchall()

        totals = conn.execute(f"""
            SELECT SUM(revenue), SUM(profit), AVG(unit_price), AVG(customer_rating)
            FROM {table}
            WHERE year = ?
        """, (latest_year,)).fetchone()
        total_revenue, total_profit, avg_price, avg_rating = totals

        yoy = conn.execute(f"""
            SELECT year, SUM(revenue)
            FROM {table}
            GROUP BY year
            ORDER BY year
        """).fetchall()

        conn.close()

        metrics = (
            f"Table used: {table}\n"
            f"Latest year: {latest_year}\n"
            f"Top companies by revenue: {top_companies}\n"
            f"Total revenue: {total_revenue:,.0f}\n"
            f"Total profit: {total_profit:,.0f}\n"
            f"Average unit price: {avg_price:.2f}\n"
            f"Average customer rating: {avg_rating:.2f}\n"
            f"Revenue by year: {yoy}"
        )
    except Exception as e:
        print(f"   ⚠️ SQL query failed: {e}")
        raise

    return {"sql_metrics": metrics}

def writer_node(state: State) -> dict:
    print("→ writer running")
    prompt = f"""Write a structured Markdown market report for {state['industry']}.

## Web Research Findings
{state['research_findings']}

## Historical Data (from internal database)
{state['sql_metrics']}

Structure the report with headings: Executive Summary, Market Trends, Historical Performance, Outlook."""
    report = llm.invoke(prompt).content

    filename = f"{state['industry'].lower().replace(' ', '_')}_report.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)

    return {"report": report}


def supervisor_node(state: State) -> dict:
    print("→ supervisor deciding")
    if not state.get("research_findings"):
        next_step = "researcher"
    elif not state.get("sql_metrics"):
        next_step = "sql_analyst"
    elif not state.get("report"):
        next_step = "writer"
    else:
        next_step = "done"

    print(f"   picked: {next_step}")
    return {"next_step": next_step, "loop_count": state["loop_count"] + 1}


graph = StateGraph(State)
graph.add_node("supervisor", supervisor_node)
graph.add_node("researcher", researcher_node)
graph.add_node("sql_analyst", sql_analyst_node)
graph.add_node("writer", writer_node)

graph.add_edge(START, "supervisor")
graph.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {"researcher": "researcher", "sql_analyst": "sql_analyst", "writer": "writer", "done": END},
)
graph.add_edge("researcher", "supervisor")
graph.add_edge("sql_analyst", "supervisor")
graph.add_edge("writer", "supervisor")

graph_app = graph.compile()

if __name__ == "__main__":
    industry = input("Enter industry to research: ")
    result = graph_app.invoke({
        "industry": industry,
        "research_findings": None,
        "sql_metrics": None,
        "report": None,
        "next_step": "",
        "loop_count": 0,
    })
    print("\nreport saved.")