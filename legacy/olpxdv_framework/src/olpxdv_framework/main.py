"""
Main entry point for the OLP XDV Framework.

This module serves as the desktop application entry point,
initializing and coordinating all components of the framework.
"""

from __future__ import annotations
import asyncio
import logging
import signal
import sys
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from ...config.settings import get_settings
from ...application.scan_pipeline import ScanPipeline
from ...application.trigger_pipeline import TriggerPipeline
from ...application.publish_pipeline import PublishPipeline
from ...domain.clv_calculator import CLVCalculator
from ...domain.knowledge_persistence import KnowledgePersistenceService
from ...infrastructure.telegram_adapter import TelegramAdapter, MockTelegramAdapter
from ...infrastructure.sportybet_bridge import SportybetBridge
from ...infrastructure.web_dashboard import app as dashboard_app
from ...infrastructure.vault_memory_sync import vault_memory_sync

logger = logging.getLogger(__name__)


class OLPXDVApplication:
    """
    Main application class for the OLP XDV Framework.

    Coordinates:
    - Pipeline execution (SCAN → TRIGGER → PUBLISH)
    - External adapters (Telegram, SportyBet, etc.)
    - Web dashboard
    - Vault-memory synchronization
    - Graceful shutdown handling
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Core services
        self.clv_calculator = CLVCalculator()
        self.knowledge_service = KnowledgePersistenceService()

        # Pipelines
        self.scan_pipeline = ScanPipeline()
        self.trigger_pipeline = TriggerPipeline(
            clv_calculator=self.clv_calculator,
            knowledge_service=self.knowledge_service
        )
        self.publish_pipeline = PublishPipeline(
            clv_calculator=self.clv_calculator,
            knowledge_service=self.knowledge_service
        )

        # Adapters
        self.telegram_adapter = self._initialize_telegram_adapter()
        self.sportybet_bridge = SportybetBridge()

        # Background tasks
        self._background_tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

        # Application state
        self._is_running = False

    def _initialize_telegram_adapter(self) -> TelegramAdapter:
        """Initialize Telegram adapter based on configuration."""
        if self.settings.api.telegram_bot_token and self.settings.api.telegram_chat_id:
            self.logger.info("Initializing real Telegram adapter")
            return TelegramAdapter()
        else:
            self.logger.info("Initializing mock Telegram adapter (no credentials)")
            return MockTelegramAdapter()

    async def startup(self):
        """Initialize all application components."""
        self.logger.info("Starting OLP XDV Framework...")

        try:
            # Initialize core services
            await self._initialize_services()

            # Start background tasks
            await self._start_background_tasks()

            # Start web dashboard
            await self._start_web_dashboard()

            self._is_running = True
            self.logger.info("OLP XDV Framework started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start OLP XDV Framework: {e}")
            await self.shutdown()
            raise

    async def _initialize_services(self):
        """Initialize individual services."""
        self.logger.info("Initializing core services...")

        # Test Telegram connectivity
        telegram_healthy = await self.telegram_adapter.health_check()
        self.logger.info(f"Telegram adapter health: {'OK' if telegram_healthy else 'FAILED'}")

        # Test SportyBet bridge
        sportybet_healthy = await self.sportybet_bridge.health_check()
        self.logger.info(f"SportyBet bridge health: {'OK' if sportybet_healthy else 'FAILED'}")

        # Initialize pipelines
        await self.scan_pipeline.initialize()
        await self.trigger_pipeline.initialize()
        await self.publish_pipeline.initialize()

        self.logger.info("Core services initialized")

    async def _start_background_tasks(self):
        """Start background tasks for pipeline execution."""
        self.logger.info("Starting background tasks...")

        # Start pipeline execution tasks
        scan_task = asyncio.create_task(self._run_scan_pipeline_continuously())
        trigger_task = asyncio.create_task(self._run_trigger_pipeline_continuously())
        publish_task = asyncio.create_task(self._run_publish_pipeline_continuously())
        sync_task = asyncio.create_task(self._run_vault_memory_sync_continuously())

        self._background_tasks.update([scan_task, trigger_task, publish_task, sync_task])

        # Start health monitoring task
        health_task = asyncio.create_task(self._monitor_health())
        self._background_tasks.add(health_task)

        self.logger.info(f"Started {len(self._background_tasks)} background tasks")

    async def _run_scan_pipeline_continuously(self):
        """Run SCAN pipeline continuously at configured intervals."""
        interval = self.settings.framework.scan_interval_seconds
        self.logger.info(f"Starting SCAN pipeline with {interval}s interval")

        while not self._shutdown_event.is_set():
            try:
                await self.scan_pipeline.run_scan_cycle()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in SCAN pipeline: {e}")
                await asyncio.sleep(min(interval, 60))  # Wait at least a minute before retrying

    async def _run_trigger_pipeline_continuously(self):
        """Run TRIGGER pipeline continuously at configured intervals."""
        interval = self.settings.framework.trigger_interval_seconds
        self.logger.info(f"Starting TRIGGER pipeline with {interval}s interval")

        while not self._shutdown_event.is_set():
            try:
                # Get consensus from SCAN pipeline (in a real implementation, this would come from a queue/cache)
                consensus_list = []  # Placeholder - would be populated from SCAN results
                if consensus_list:
                    await self.trigger_pipeline.run_trigger_cycle(consensus_list)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in TRIGGER pipeline: {e}")
                await asyncio.sleep(min(interval, 60))

    async def _run_publish_pipeline_continuously(self):
        """Run PUBLISH pipeline continuously at configured intervals."""
        interval = self.settings.framework.publish_interval_seconds
        self.logger.info(f"Starting PUBLISH pipeline with {interval}s interval")

        while not self._shutdown_event.is_set():
            try:
                # Get trigger results from TRIGGER pipeline (placeholder)
                trigger_results = []  # Would be populated from TRIGGER results
                if trigger_results:
                    await self.publish_pipeline.run_publish_cycle(trigger_results)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in PUBLISH pipeline: {e}")
                await asyncio.sleep(min(interval, 60))

    async def _run_vault_memory_sync_continuously(self):
        """Run vault-memory synchronization continuously."""
        interval = self.settings.framework.vault_memory_sync_interval_seconds
        self.logger.info(f"Starting vault-memory sync with {interval}s interval")

        while not self._shutdown_event.is_set():
            try:
                await vault_memory_sync.sync_bidirectional()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in vault-memory sync: {e}")
                await asyncio.sleep(min(interval, 60))

    async def _monitor_health(self):
        """Monitor application health and log status."""
        self.logger.info("Starting health monitoring...")

        while not self._shutdown_event.is_set():
            try:
                # Log periodic status
                self.logger.info("Application health check:")
                self.logger.info(f"  - Running: {self._is_running}")
                self.logger.info(f"  - Background tasks: {len([t for t in self._background_tasks if not t.done()])}/{len(self._background_tasks)}")

                # Check component health
                telegram_healthy = await self.telegram_adapter.health_check()
                self.logger.info(f"  - Telegram: {'HEALTHY' if telegram_healthy else 'UNHEALTHY'}")

                sportybet_healthy = await self.sportybet_bridge.health_check()
                self.logger.info(f"  - SportyBet: {'HEALTHY' if sportybet_healthy else 'UNHEALTHY'}")

                # Log CLV gate status
                clv_status = self.clv_calculator.get_clv_gate_status()
                self.logger.info(f"  - CLV Gate: {clv_status}")

                await asyncio.sleep(300)  # Health check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)

    async def _start_web_dashboard(self):
        """Start the web dashboard server."""
        self.logger.info("Starting web dashboard...")

        # Configure uvicorn
        config = uvicorn.Config(
            app=dashboard_app,
            host=self.settings.dashboard.host,
            port=self.settings.dashboard.port,
            log_level="info",
            access_log=True
        )

        server = uvicorn.Server(config)

        # Run server in background task
        dashboard_task = asyncio.create_task(server.serve())
        self._background_tasks.add(dashboard_task)

        self.logger.info(f"Web dashboard started on http://{self.settings.dashboard.host}:{self.settings.dashboard.port}")

    async def shutdown(self):
        """Gracefully shutdown all application components."""
        if not self._is_running:
            return

        self.logger.info("Shutting down OLP XDV Framework...")
        self._shutdown_event.set()
        self._is_running = False

        # Cancel all background tasks
        if self._background_tasks:
            self.logger.info(f"Cancelling {len(self._background_tasks)} background tasks...")
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete (with timeout)
            if self._background_tasks:
                await asyncio.wait(
                    self._background_tasks,
                    timeout=30.0,
                    return_when=asyncio.ALL_COMPLETED
                )

        # Shutdown individual components
        try:
            await self.scan_pipeline.shutdown()
            await self.trigger_pipeline.shutdown()
            await self.publish_pipeline.shutdown()
            await self.sportybet_bridge.close()  # If it has a close method
        except Exception as e:
            self.logger.error(f"Error during component shutdown: {e}")

        self.logger.info("OLP XDV Framework shutdown complete")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("olpxdv.log")
        ]
    )

    # Create and start application
    app = OLPXDVApplication()
    app.setup_signal_handlers()

    try:
        await app.startup()

        # Wait for shutdown signal
        await app._shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Run the application
    asyncio.run(main())