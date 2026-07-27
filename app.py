from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from market_research import graph_app  

app = FastAPI(title="Market Research Agent API")

class ReportRequest(BaseModel):
    industry: str

@app.get("/")
def health_check():
    return {"status": "running"}

@app.post("/generate-report")
def generate_report(req: ReportRequest):
    try:
        result = graph_app.invoke({
            "industry": req.industry,
            "research_findings": None,
            "sql_metrics": None,
            "report": None,
            "next_step": "",
            "loop_count": 0,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "industry": req.industry,
        "report": result["report"],
        "sql_metrics": result["sql_metrics"],
    }
