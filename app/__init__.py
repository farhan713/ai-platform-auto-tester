"""Skylar IQ SQL Agent — generic QA automation tool.

Re-usable across any Celerant Back Office tenant: the operator supplies the
login URL, credentials, and an .xlsx of natural-language questions; the tool
drives the real Skylar IQ UI through Playwright, captures every API call, and
produces an HTML/Markdown/JSON report.
"""

__version__ = "1.0.0"
