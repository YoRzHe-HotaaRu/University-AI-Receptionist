"""
Expression Mapper for VTube Studio
Maps Aiko's emotion tags to Live2D expressions.
"""

import re
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class ExpressionConfig:
    """Configuration for a single expression mapping."""
    emotion_tag: str        # Aiko emotion tag (e.g., "HAPPY")
    expression_file: str    # VTS expression file (e.g., "happy.exp3.json")
    hotkey_id: str = ""     # Optional hotkey ID as alternative trigger


class ExpressionMapper:
    """
    Maps Aiko's emotion tags to VTube Studio expressions.
    Supports both expression files and hotkey-based activation.
    """
    
    # Default emotion tag patterns
    EMOTION_PATTERN = re.compile(r'\[(NEUTRAL|HAPPY|SHY|TSUNDERE|SAD|SURPRISED)\]')
    
    # Default expression mappings
    # Users can customize these to match their model's expression files
    DEFAULT_MAPPINGS: Dict[str, str] = {
        "NEUTRAL": "neutral.exp3.json",
        "HAPPY": "happy.exp3.json",
        "SHY": "shy.exp3.json",
        "TSUNDERE": "tsundere.exp3.json",
        "SAD": "sad.exp3.json",
        "SURPRISED": "surprised.exp3.json"
    }
    
    def __init__(self, 
                 expression_mappings: Dict[str, str] = None,
                 hotkey_mappings: Dict[str, str] = None,
                 use_hotkeys: bool = False):
        """
        Initialize the expression mapper.
        
        Args:
            expression_mappings: Dict of emotion -> expression file (uses defaults if None)
            hotkey_mappings: Dict of emotion -> hotkey ID (for models using hotkeys)
            use_hotkeys: If True, use hotkeys instead of expression files
        """
        self.expression_mappings = expression_mappings or self.DEFAULT_MAPPINGS.copy()
        self.hotkey_mappings = hotkey_mappings or {}
        self.use_hotkeys = use_hotkeys
        self._current_expression = None
        self._available_expressions: List[str] = []
        self._available_hotkeys: List[str] = []
        
    def extract_emotion(self, text: str) -> Optional[str]:
        """
        Extract emotion tag from AI response text.
        
        Args:
            text: Full AI response text
            
        Returns:
            Emotion name (e.g., "HAPPY") or None if not found
        """
        match = self.EMOTION_PATTERN.search(text)
        return match.group(1) if match else None
    
    def get_expression_file(self, emotion: str) -> Optional[str]:
        """
        Get the expression file for an emotion.
        
        Args:
            emotion: Emotion name (e.g., "HAPPY")
            
        Returns:
            Expression filename or None if not mapped
        """
        return self.expression_mappings.get(emotion.upper())
    
    def get_hotkey_id(self, emotion: str) -> Optional[str]:
        """
        Get the hotkey ID for an emotion.
        
        Args:
            emotion: Emotion name (e.g., "HAPPY")
            
        Returns:
            Hotkey ID or None if not mapped
        """
        return self.hotkey_mappings.get(emotion.upper())
    
    async def update_expression(self, vts_connector, text: str) -> bool:
        """
        Extract emotion from text and update VTube Studio expression.
        
        Args:
            vts_connector: VTSConnector instance
            text: AI response text containing emotion tag
            
        Returns:
            True if expression was updated
        """
        emotion = self.extract_emotion(text)
        if not emotion:
            return False
            
        # Check if already showing this expression
        if emotion == self._current_expression:
            return False
        
        if self.use_hotkeys:
            hotkey_id = self.get_hotkey_id(emotion)
            if hotkey_id:
                success = await vts_connector.trigger_hotkey(hotkey_id)
                if success:
                    self._current_expression = emotion
                    print(f"[Expression] Triggered hotkey for {emotion}")
                return success
        else:
            expression_file = self.get_expression_file(emotion)
            if expression_file:
                # Deactivate previous expression if any
                if self._current_expression:
                    prev_file = self.get_expression_file(self._current_expression)
                    if prev_file:
                        await vts_connector.set_expression(prev_file, active=False)
                
                # Activate new expression
                success = await vts_connector.set_expression(expression_file, active=True)
                if success:
                    self._current_expression = emotion
                    print(f"[Expression] Set expression to {emotion} ({expression_file})")
                return success
        
        return False
    
    async def sync_available_expressions(self, vts_connector):
        """
        Fetch available expressions from VTube Studio.
        Useful for validating configuration.
        
        Args:
            vts_connector: VTSConnector instance
        """
        expressions = await vts_connector.get_expressions()
        self._available_expressions = [e.get("file", "") for e in expressions]
        print(f"[Expression] Found {len(self._available_expressions)} expressions")
        
        hotkeys = await vts_connector.get_hotkeys()
        self._available_hotkeys = [h.get("hotkeyID", "") for h in hotkeys]
        print(f"[Expression] Found {len(self._available_hotkeys)} hotkeys")
    
    def validate_mappings(self) -> Dict[str, bool]:
        """
        Check which emotion mappings have valid targets.
        
        Returns:
            Dict of emotion -> is_valid
        """
        result = {}
        for emotion, expression in self.expression_mappings.items():
            if self.use_hotkeys:
                hotkey = self.hotkey_mappings.get(emotion, "")
                result[emotion] = hotkey in self._available_hotkeys
            else:
                result[emotion] = expression in self._available_expressions
        return result
    
    def reset(self):
        """Reset current expression state."""
        self._current_expression = None


# Global instance
_mapper: Optional[ExpressionMapper] = None


def get_mapper() -> ExpressionMapper:
    """Get or create the global expression mapper."""
    global _mapper
    if _mapper is None:
        _mapper = ExpressionMapper()
    return _mapper
