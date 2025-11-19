"""
Automated report generator for HP_TI.

Generates daily and weekly reports summarizing honeypot activity,
attacks detected, and system health metrics.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template
import json

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Report output formats."""

    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    MARKDOWN = "markdown"


class ReportPeriod(Enum):
    """Report time periods."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class ReportGenerator:
    """
    Generates automated reports for HP_TI platform.

    Creates comprehensive reports summarizing honeypot activity,
    attack patterns, and system performance.
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize report generator.

        Args:
            template_dir: Directory containing report templates
            output_dir: Directory for generated reports
        """
        self.template_dir = template_dir or Path(__file__).parent / "templates"
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        if self.template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=True,
            )
        else:
            self.jinja_env = None
            logger.warning(f"Template directory not found: {self.template_dir}")

        logger.info("Report generator initialized")

    async def generate_report(
        self,
        period: ReportPeriod,
        format: ReportFormat = ReportFormat.HTML,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Path:
        """
        Generate a report for the specified period.

        Args:
            period: Report period (daily, weekly, monthly)
            format: Output format (html, json, pdf, markdown)
            start_date: Start date (for custom period)
            end_date: End date (for custom period)

        Returns:
            Path to generated report file
        """
        # Calculate date range
        if period == ReportPeriod.CUSTOM:
            if not start_date or not end_date:
                raise ValueError("start_date and end_date required for custom period")
        else:
            end_date = datetime.utcnow()
            if period == ReportPeriod.DAILY:
                start_date = end_date - timedelta(days=1)
            elif period == ReportPeriod.WEEKLY:
                start_date = end_date - timedelta(days=7)
            elif period == ReportPeriod.MONTHLY:
                start_date = end_date - timedelta(days=30)

        # Collect report data
        logger.info(f"Generating {period.value} report from {start_date} to {end_date}")
        data = await self._collect_report_data(start_date, end_date)

        # Add metadata
        data["report_metadata"] = {
            "period": period.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "format": format.value,
        }

        # Generate report in requested format
        if format == ReportFormat.HTML:
            report_file = await self._generate_html_report(data, period)
        elif format == ReportFormat.JSON:
            report_file = await self._generate_json_report(data, period)
        elif format == ReportFormat.PDF:
            report_file = await self._generate_pdf_report(data, period)
        elif format == ReportFormat.MARKDOWN:
            report_file = await self._generate_markdown_report(data, period)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Report generated: {report_file}")
        return report_file

    async def _collect_report_data(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect data for report generation.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Dictionary with report data
        """
        # In production, this would query the database and metrics
        # For now, return mock data structure

        data = {
            "executive_summary": await self._get_executive_summary(start_date, end_date),
            "attack_statistics": await self._get_attack_statistics(start_date, end_date),
            "top_attackers": await self._get_top_attackers(start_date, end_date),
            "geographic_distribution": await self._get_geographic_distribution(
                start_date, end_date
            ),
            "service_statistics": await self._get_service_statistics(start_date, end_date),
            "attack_patterns": await self._get_attack_patterns(start_date, end_date),
            "credentials": await self._get_credential_statistics(start_date, end_date),
            "system_health": await self._get_system_health(start_date, end_date),
            "trends": await self._get_trends(start_date, end_date),
            "recommendations": await self._get_recommendations(start_date, end_date),
        }

        return data

    async def _get_executive_summary(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get executive summary data."""
        # TODO: Query from database/metrics
        return {
            "total_connections": 15420,
            "total_attacks": 3245,
            "unique_attackers": 892,
            "authentication_attempts": 12387,
            "commands_executed": 5621,
            "services_active": 4,
            "uptime_percentage": 99.8,
        }

    async def _get_attack_statistics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get attack statistics."""
        return {
            "by_type": {
                "brute_force": 1234,
                "sql_injection": 456,
                "xss": 234,
                "path_traversal": 321,
                "command_injection": 189,
                "reconnaissance": 811,
            },
            "by_service": {
                "ssh": 8932,
                "http": 3245,
                "telnet": 1876,
                "ftp": 1367,
            },
            "success_rate": 0.0,  # Should always be 0 for honeypots
            "average_session_duration": 127.5,  # seconds
        }

    async def _get_top_attackers(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get top attacking IPs."""
        return [
            {
                "ip": "192.0.2.1",
                "country": "CN",
                "attacks": 234,
                "services": ["ssh", "telnet"],
                "threat_score": 95,
            },
            {
                "ip": "192.0.2.2",
                "country": "RU",
                "attacks": 189,
                "services": ["http", "ftp"],
                "threat_score": 87,
            },
            {
                "ip": "192.0.2.3",
                "country": "US",
                "attacks": 156,
                "services": ["ssh"],
                "threat_score": 72,
            },
        ]

    async def _get_geographic_distribution(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, int]:
        """Get geographic distribution of attacks."""
        return {
            "CN": 4521,
            "RU": 3245,
            "US": 2891,
            "BR": 1234,
            "IN": 987,
            "KR": 876,
            "DE": 654,
            "GB": 543,
            "FR": 432,
            "JP": 321,
        }

    async def _get_service_statistics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """Get per-service statistics."""
        return {
            "ssh": {
                "connections": 8932,
                "auth_attempts": 7821,
                "unique_credentials": 1245,
                "uptime": 99.9,
            },
            "http": {
                "requests": 3245,
                "attacks": 892,
                "unique_paths": 456,
                "uptime": 99.8,
            },
            "telnet": {
                "connections": 1876,
                "auth_attempts": 1654,
                "unique_credentials": 432,
                "uptime": 99.7,
            },
            "ftp": {
                "connections": 1367,
                "auth_attempts": 1112,
                "file_operations": 234,
                "uptime": 99.9,
            },
        }

    async def _get_attack_patterns(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get detected attack patterns."""
        return [
            {
                "pattern": "Mirai Botnet",
                "occurrences": 234,
                "ips_involved": 156,
                "services": ["telnet", "ssh"],
            },
            {
                "pattern": "SSH Brute Force",
                "occurrences": 892,
                "ips_involved": 234,
                "services": ["ssh"],
            },
            {
                "pattern": "Web Scanner",
                "occurrences": 456,
                "ips_involved": 123,
                "services": ["http"],
            },
        ]

    async def _get_credential_statistics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get credential statistics."""
        return {
            "total_unique_credentials": 2345,
            "total_unique_usernames": 1234,
            "total_unique_passwords": 1987,
            "top_usernames": [
                {"username": "admin", "count": 1234},
                {"username": "root", "count": 987},
                {"username": "user", "count": 654},
                {"username": "test", "count": 432},
                {"username": "guest", "count": 321},
            ],
            "top_passwords": [
                {"password": "123456", "count": 892},
                {"password": "password", "count": 765},
                {"password": "admin", "count": 543},
                {"password": "12345678", "count": 432},
                {"password": "root", "count": 321},
            ],
        }

    async def _get_system_health(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get system health metrics."""
        return {
            "services": {
                "ssh": {"status": "up", "uptime": 99.9},
                "http": {"status": "up", "uptime": 99.8},
                "telnet": {"status": "up", "uptime": 99.7},
                "ftp": {"status": "up", "uptime": 99.9},
            },
            "pipeline": {
                "events_processed": 45821,
                "processing_errors": 12,
                "average_latency_ms": 45.3,
                "queue_size_avg": 234,
            },
            "storage": {
                "postgres": {"status": "healthy", "connection_pool": 8},
                "elasticsearch": {"status": "healthy", "documents": 892345},
                "redis": {"status": "healthy", "cache_hit_rate": 0.78},
            },
        }

    async def _get_trends(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get trend analysis."""
        return {
            "attack_rate_change": "+15%",
            "unique_ips_change": "+23%",
            "new_attack_patterns": 3,
            "emerging_threats": [
                "New IoT botnet variant detected",
                "Increase in Log4j exploitation attempts",
            ],
        }

    async def _get_recommendations(
        self, start_date: datetime, end_date: datetime
    ) -> List[str]:
        """Get security recommendations."""
        return [
            "Block IP range 192.0.2.0/24 showing persistent brute force behavior",
            "Update threat intelligence feeds to detect new botnet variant",
            "Review and update honeypot banners for telnet service",
            "Investigate coordinated attack pattern from Chinese IP addresses",
        ]

    async def _generate_html_report(
        self, data: Dict[str, Any], period: ReportPeriod
    ) -> Path:
        """Generate HTML report."""
        if not self.jinja_env:
            raise RuntimeError("Template environment not initialized")

        # Use template if available, otherwise create simple HTML
        try:
            template = self.jinja_env.get_template(f"{period.value}_report.html")
        except Exception:
            template = Template(self._get_default_html_template())

        html_content = template.render(**data)

        # Save report
        filename = self._generate_filename(period, ReportFormat.HTML)
        report_path = self.output_dir / filename
        report_path.write_text(html_content)

        return report_path

    async def _generate_json_report(
        self, data: Dict[str, Any], period: ReportPeriod
    ) -> Path:
        """Generate JSON report."""
        filename = self._generate_filename(period, ReportFormat.JSON)
        report_path = self.output_dir / filename

        with open(report_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return report_path

    async def _generate_pdf_report(
        self, data: Dict[str, Any], period: ReportPeriod
    ) -> Path:
        """Generate PDF report."""
        # First generate HTML
        html_path = await self._generate_html_report(data, period)

        # Convert HTML to PDF using weasyprint
        try:
            from weasyprint import HTML

            filename = self._generate_filename(period, ReportFormat.PDF)
            pdf_path = self.output_dir / filename

            HTML(filename=str(html_path)).write_pdf(str(pdf_path))

            logger.info(f"PDF report generated: {pdf_path}")
            return pdf_path

        except ImportError:
            logger.error("weasyprint not installed, cannot generate PDF")
            raise RuntimeError("PDF generation requires weasyprint library")

    async def _generate_markdown_report(
        self, data: Dict[str, Any], period: ReportPeriod
    ) -> Path:
        """Generate Markdown report."""
        md_content = self._format_markdown_report(data, period)

        filename = self._generate_filename(period, ReportFormat.MARKDOWN)
        report_path = self.output_dir / filename
        report_path.write_text(md_content)

        return report_path

    def _format_markdown_report(
        self, data: Dict[str, Any], period: ReportPeriod
    ) -> str:
        """Format data as Markdown."""
        meta = data["report_metadata"]
        summary = data["executive_summary"]
        attacks = data["attack_statistics"]

        md = f"""# HP_TI {period.value.title()} Report

**Generated**: {meta['generated_at']}
**Period**: {meta['start_date']} to {meta['end_date']}

---

## Executive Summary

- **Total Connections**: {summary['total_connections']:,}
- **Total Attacks**: {summary['total_attacks']:,}
- **Unique Attackers**: {summary['unique_attackers']:,}
- **Authentication Attempts**: {summary['authentication_attempts']:,}
- **System Uptime**: {summary['uptime_percentage']}%

## Attack Statistics

### By Type
"""
        for attack_type, count in attacks['by_type'].items():
            md += f"- **{attack_type.replace('_', ' ').title()}**: {count:,}\n"

        md += "\n### By Service\n"
        for service, count in attacks['by_service'].items():
            md += f"- **{service.upper()}**: {count:,}\n"

        md += f"\n## Top Attackers\n\n"
        for idx, attacker in enumerate(data['top_attackers'][:5], 1):
            md += f"{idx}. **{attacker['ip']}** ({attacker['country']}) - {attacker['attacks']} attacks\n"

        md += f"\n## Recommendations\n\n"
        for idx, rec in enumerate(data['recommendations'], 1):
            md += f"{idx}. {rec}\n"

        return md

    def _generate_filename(self, period: ReportPeriod, format: ReportFormat) -> str:
        """Generate report filename."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"hp_ti_report_{period.value}_{timestamp}.{format.value}"

    def _get_default_html_template(self) -> str:
        """Get default HTML template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>HP_TI Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        .metric { display: inline-block; margin: 15px; padding: 20px; background: #f0f0f0; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>HP_TI {{ report_metadata.period|title }} Report</h1>
    <p>Generated: {{ report_metadata.generated_at }}</p>

    <h2>Executive Summary</h2>
    <div class="metric">Total Connections: {{ executive_summary.total_connections }}</div>
    <div class="metric">Total Attacks: {{ executive_summary.total_attacks }}</div>
    <div class="metric">Unique Attackers: {{ executive_summary.unique_attackers }}</div>

    <h2>Attack Statistics</h2>
    <table>
        <tr><th>Attack Type</th><th>Count</th></tr>
        {% for type, count in attack_statistics.by_type.items() %}
        <tr><td>{{ type }}</td><td>{{ count }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""


# Global report generator instance
_report_generator: Optional[ReportGenerator] = None


def get_report_generator(
    template_dir: Optional[Path] = None, output_dir: Optional[Path] = None
) -> ReportGenerator:
    """
    Get global report generator instance.

    Args:
        template_dir: Template directory (only used on first call)
        output_dir: Output directory (only used on first call)

    Returns:
        ReportGenerator instance
    """
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator(template_dir, output_dir)
    return _report_generator
