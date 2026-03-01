"""
VTube Studio Integration for Aiko AI Companion
Enables Live2D avatar control via VTube Studio API.
"""

from .vts_connector import VTSConnector
from .lip_sync import LipSyncAnalyzer
from .expressions import ExpressionMapper

__all__ = ['VTSConnector', 'LipSyncAnalyzer', 'ExpressionMapper']
