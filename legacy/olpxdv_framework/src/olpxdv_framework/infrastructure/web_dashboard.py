"""
Web Dashboard for OLP XDV Framework.

This module implements a FastAPI-based web dashboard for monitoring
the OLP XDV framework, displaying pipeline status, CLV metrics,
and betting recommendations.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import uvicorn

from olpxdv_framework.domain.models import EngineConsensus, MarketType
from olpxdv_framework.domain.clv_calculator import CLVCalculator
from olpxdv_framework.domain.protected_constants import (
    get_current_phase,
    is_client_publish_enabled,
    is_paper_only,
    ProtectedConstants
)
from olpxdv_framework.domain.knowledge_persistence import KnowledgePersistenceService
from olpxdv_framework.application.scan_pipeline import ScanPipeline
from olpxdv_framework.application.trigger_pipeline import TriggerPipeline
from olpxdv_framework.application.publish_pipeline import PublishPipeline
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OLP XDV Dashboard",
    description="Web dashboard for monitoring the OLP XDV sports betting calibration framework",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files (if we had any)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates (if we had any)
# templates = Jinja2Templates(directory="templates")

# Initialize services
settings = get_settings()
clv_calculator = CLVCalculator()
knowledge_service = KnowledgePersistenceService()
scan_pipeline = ScanPipeline()
trigger_pipeline = TriggerPipeline(clv_calculator=clv_calculator, knowledge_service=knowledge_service)
# Note: PublishPipeline is not instantiated here to avoid circular import
# It will be created when needed by the application


# Pydantic models for API responses
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime_seconds: float


class PipelineStatusResponse(BaseModel):
    pipeline: str
    status: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class CLVMetricsResponse(BaseModel):
    total_legs: int
    open_legs: int
    closed_legs: int
    winning_legs: int
    losing_legs: int
    total_clv: float
    average_clv: float
    clv_gate_status: str
    clv_mean_threshold: float
    clv_min_legs: int


class ConsensusResponse(BaseModel):
    fixture_id: str
    market_type: str
    selection: str
    probability: float
    expected_value: float
    confidence: float
    kelly_fraction: float
    engines_used: List[str]
    timestamp: str


class TriggerResultResponse(BaseModel):
    fixture_id: str
    market_type: str
    selection: str
    expected_value: float
    edge: float
    recommended_stake: float
    kelly_fraction: float
    trigger_passed: bool
    trigger_reason: str
    consensus: ConsensusResponse


class KnowledgeItemResponse(BaseModel):
    id: str
    content: str
    tags: List[str]
    relevance_score: float
    created_at: str
    expires_at: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    health: HealthResponse
    pipeline_status: Dict[str, PipelineStatusResponse]
    clv_metrics: CLVMetricsResponse
    recent_consensus: List[ConsensusResponse]
    recent_triggers: List[TriggerResultResponse]
    recent_knowledge: List[KnowledgeItemResponse]
    protected_constants: Dict[str, Any]


# Startup time for uptime calculation
_startup_time = datetime.utcnow()


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("OLP XDV Dashboard starting up...")
    # In a real implementation, we might start background tasks here


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("OLP XDV Dashboard shutting down...")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint returning a simple HTML dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OLP XDV Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
            .card { background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .metric { display: inline-block; margin: 10px; padding: 15px; background-color: #ecf0f1; border-radius: 5px; min-width: 150px; text-align: center; }
            .metric-value { font-size: 24px; font-weight: bold; color: #2c3e50; }
            .metric-label { font-size: 14px; color: #7f8c8d; }
            .status-good { color: #27ae60; }
            .status-warning { color: #f39c12; }
            .status-error { color: #e74c3c; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
        </title>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>OLP XDV Dashboard</h1>
                <p>Sports Betting Calibration Framework</p>
            </div>

            <div class="card">
                <h2>System Status</h2>
                <div id="system-status">Loading...</div>
            </div>

            <div class="card">
                <h2>Pipeline Status</h2>
                <div id="pipeline-status">Loading...</div>
            </div>

            <div class="card">
                <h2>CLV Metrics</h2>
                <div id="clv-metrics">Loading...</div>
            </div>

            <div class="card">
                <h2>Recent Activity</h2>
                <div id="recent-activity">Loading...</div>
            </div>

            <div class="card">
                <h2>Protected Constants</h2>
                <div id="protected-constants">Loading...</div>
            </div>
        </div>

        <script>
            // Fetch data from API endpoints and update the dashboard
            async function fetchData() {
                try {
                    const [healthResp, pipelineResp, clvResp, constantsResp] = await Promise.all([
                        fetch('/api/health'),
                        fetch('/api/pipeline/status'),
                        fetch('/api/clv/metrics'),
                        fetch('/api/constants')
                    ]);

                    const health = await healthResp.json();
                    const pipelineStatus = await pipelineResp.json();
                    const clvMetrics = await clvResp.json();
                    const protectedConstants = await constantsResp.json();

                    // Update system status
                    document.getElementById('system-status').innerHTML = `
                        <div class="metric">
                            <div class="metric-value">${health.uptime_seconds.toFixed(0)}s</div>
                            <div class="metric-label">Uptime</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value ${health.status === 'healthy' ? 'status-good' : 'status-error'}">${health.status}</div>
                            <div class="metric-label">Status</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${new Date(health.timestamp).toLocaleTimeString()}</div>
                            <div class="metric-label">Time</div>
                        </div>
                    `;

                    // Update pipeline status
                    let pipelineHtml = '';
                    for (const [pipelineName, status] of Object.entries(pipelineStatus)) {
                        pipelineHtml += `
                            <div class="metric">
                                <div class="metric-value">${status.status}</div>
                                <div class="metric-label">${pipelineName}</div>
                            </div>
                        `;
                    }
                    document.getElementById('pipeline-status').innerHTML = pipelineHtml;

                    // Update CLV metrics
                    document.getElementById('clv-metrics').innerHTML = `
                        <div class="metric">
                            <div class="metric-value">${clvMetrics.total_legs}</div>
                            <div class="metric-label">Total Legs</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${clvMetrics.open_legs}</div>
                            <div class="metric-label">Open Legs</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${clvMetrics.closing_legs || clvMetrics.closed_legs}</div>
                            <div class="metric-label">Closed Legs</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${clvMetrics.total_clv.toFixed(4)}</div>
                            <div class="metric-label">Total CLV</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${clvMetrics.average_clv.toFixed(4)}</div>
                            <div class="metric-label">Avg CLV</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value ${clvMetrics.clv_gate_status === 'OPEN' ? 'status-good' : 'status-error'}">${clvMetrics.clv_gate_status}</div>
                            <div class="metric-label">CLV Gate</div>
                        </div>
                    `;

                    // Update protected constants
                    let constantsHtml = '';
                    for (const [key, value] of Object.entries(protectedConstants)) {
                        constantsHtml += `
                            <div class="metric">
                                <div class="metric-value">${typeof value === 'boolean' ? (value ? 'ENABLED' : 'DISABLED') : value}</div>
                                <div class="metric-label">${key}</div>
                            </div>
                        `;
                    }
                    document.getElementById('protected-constants').innerHTML = constantsHtml;

                } catch (error) {
                    console.error('Error fetching dashboard data:', error);
                    document.getElementById('system-status').innerHTML = '<div class="metric status-error">Error loading data</div>';
                }
            }

            // Fetch data on load and refresh every 30 seconds
            fetchData();
            setInterval(fetchData, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = (datetime.utcnow() - _startup_time).total_seconds()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
        uptime_seconds=uptime
    )


@app.get("/api/pipeline/status", response_model=Dict[str, PipelineStatusResponse])
async def get_pipeline_status():
    """Get status of all pipelines."""
    try:
        # Get status from each pipeline
        scan_status = await scan_pipeline.get_pipeline_status() if hasattr(scan_pipeline, 'get_pipeline_status') else {
            "pipeline": "SCAN",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {},
            "state": {},
            "components": {}
        }

        trigger_status = await trigger_pipeline.get_pipeline_status()
        publish_status = await publish_pipeline.get_pipeline_status() if hasattr(publish_pipeline, 'get_pipeline_status') else {
            "pipeline": "PUBLISH",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {},
            "state": {},
            "components": {}
        }

        return {
            "SCAN": PipelineStatusResponse(
                pipeline="SCAN",
                status="active",
                last_run=scan_status.get("timestamp"),
                metrics=scan_status.get("state", {})
            ),
            "TRIGGER": PipelineStatusResponse(
                pipeline="TRIGGER",
                status="active",
                last_run=trigger_status.get("timestamp"),
                metrics=trigger_status.get("state", {})
            ),
            "PUBLISH": PipelineStatusResponse(
                pipeline="PUBLISH",
                status="active",
                last_run=publish_status.get("timestamp"),
                metrics=publish_status.get("state", {})
            )
        }
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        # Return default status on error
        return {
            "SCAN": PipelineStatusResponse(pipeline="SCAN", status="error"),
            "TRIGGER": PipelineStatusResponse(pipeline="TRIGGER", status="error"),
            "PUBLISH": PipelineStatusResponse(pipeline="PUBLISH", status="error")
        }


@app.get("/api/clv/metrics", response_model=CLVMetricsResponse)
async def get_clv_metrics():
    """Get CLV metrics."""
    try:
        summary = clv_calculator.get_clv_performance_summary()
        gate_status = clv_calculator.get_clv_gate_status()

        return CLVMetricsResponse(
            total_legs=summary.get("total_legs", 0),
            open_legs=summary.get("open_legs", 0),
            closed_legs=summary.get("closed_legs", 0),
            winning_legs=summary.get("winning_legs", 0),
            losing_legs=summary.get("losing_legs", 0),
            total_clv=summary.get("total_clv", 0.0),
            average_clv=summary.get("average_clv", 0.0),
            clv_gate_status=gate_status,
            clv_mean_threshold=float(get_clv_mean_threshold()),
            clv_min_legs=get_clv_min_legs()
        )
    except Exception as e:
        logger.error(f"Error getting CLV metrics: {e}")
        # Return default values on error
        return CLVMetricsResponse(
            total_legs=0,
            open_legs=0,
            closed_legs=0,
            winning_legs=0,
            losing_legs=0,
            total_clv=0.0,
            average_clv=0.0,
            clv_gate_status="ERROR",
            clv_mean_threshold=0.0,
            clv_min_legs=0
        )


@app.get("/api/consensus/recent", response_model=List[ConsensusResponse])
async def get_recent_consensus(limit: int = 10):
    """Get recent engine consensus."""
    # In a real implementation, this would fetch from a database or cache
    # For now, return empty list
    return []


@app.get("/api/triggers/recent", response_model=List[TriggerResultResponse])
async def get_recent_triggers(limit: int = 10):
    """Get recent trigger results."""
    # In a real implementation, this would fetch from a database or cache
    # For now, return empty list
    return []


@app.get("/api/knowledge/recent", response_model=List[KnowledgeItemResponse])
async def get_recent_knowledge(limit: int = 10):
    """Get recent knowledge items."""
    try:
        # Search for recent knowledge items
        items = knowledge_service.search_by_content("", limit=limit)

        return [
            KnowledgeItemResponse(
                id=item.id,
                content=item.content[:200] + "..." if len(item.content) > 200 else item.content,
                tags=item.tags,
                relevance_score=item.relevance_score,
                created_at=item.created_at.isoformat(),
                expires_at=item.expires_at.isoformat() if item.expires_at else None
            )
            for item in items
        ]
    except Exception as e:
        logger.error(f"Error getting recent knowledge: {e}")
        return []


@app.get("/api/constants", response_model=Dict[str, Any])
async def get_protected_constants():
    """Get current values of protected constants."""
    try:
        constants = {}
        # Get all protected constants
        for name in ProtectedConstants._constants.keys():
            try:
                # Use the getter function if it exists, otherwise get the raw value
                if hasattr(ProtectedConstants, f"get_{name.lower()}"):
                    getter = getattr(ProtectedConstants, f"get_{name.lower()}")
                    constants[name] = getter()
                else:
                    constants[name] = ProtectedConstants._constants[name].value
            except Exception:
                # If we can't get it via getter, try to get the raw value
                constants[name] = ProtectedConstants._constants.get(name, {}).get("value", "UNKNOWN")

        return constants
    except Exception as e:
        logger.error(f"Error getting protected constants: {e}")
        return {"error": str(e)}


@app.post("/api/pipeline/scan/run")
async def run_scan_pipeline(background_tasks: BackgroundTasks):
    """Manually trigger a SCAN pipeline run."""
    try:
        # Run in background to avoid blocking the API
        background_tasks.add_task(scan_pipeline.run_scan_cycle)
        return {"status": "started", "message": "SCAN pipeline started in background"}
    except Exception as e:
        logger.error(f"Error starting SCAN pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/trigger/run")
async def run_trigger_pipeline(background_tasks: BackgroundTasks):
    """Manually trigger a TRIGGER pipeline run."""
    try:
        # Run in background to avoid blocking the API
        background_tasks.add_task(trigger_pipeline.run_trigger_cycle, [])
        return {"status": "started", "message": "TRIGGER pipeline started in background"}
    except Exception as e:
        logger.error(f"Error starting TRIGGER pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/publish/run")
async def run_publish_pipeline(background_tasks: BackgroundTasks):
    """Manually trigger a PUBLISH pipeline run."""
    try:
        # Run in background to avoid blocking the API
        background_tasks.add_task(publish_pipeline.run_publish_cycle, [])
        return {"status": "started", "message": "PUBLISH pipeline started in background"}
    except Exception as e:
        logger.error(f"Error starting PUBLISH pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/docs")
async def get_api_docs():
    """Redirect to automatic API docs."""
    return {"message": "API documentation available at /docs and /redoc"}


def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    return app


def run_dashboard(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the dashboard server."""
    uvicorn.run("src.infrastructure.web_dashboard:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_dashboard(reload=True)