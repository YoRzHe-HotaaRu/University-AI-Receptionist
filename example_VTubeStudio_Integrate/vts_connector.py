"""
VTube Studio WebSocket Connector
Handles communication with VTube Studio API for Live2D model control.
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class VTSConnector:
    """
    WebSocket connector for VTube Studio Plugin API.
    Manages authentication, parameter injection, and expression triggers.
    """
    
    # Plugin identification
    PLUGIN_NAME = "Aiko AI Companion"
    PLUGIN_DEVELOPER = "Aiko"
    PLUGIN_ICON = None  # Optional: base64 encoded icon
    
    def __init__(self, host: str = "localhost", port: int = 8001):
        """
        Initialize VTS connector.
        
        Args:
            host: VTube Studio host (default: localhost)
            port: VTube Studio API port (default: 8001)
        """
        self.host = host
        self.port = port
        self.websocket = None
        self.authenticated = False
        self.auth_token = None
        self._request_id = 0
        self._token_path = Path(__file__).parent / ".vts_token"
        self._load_token()
        
    def _load_token(self):
        """Load saved authentication token if exists."""
        if self._token_path.exists():
            try:
                self.auth_token = self._token_path.read_text().strip()
                print(f"[VTS] Loaded saved auth token")
            except Exception as e:
                print(f"[VTS] Could not load token: {e}")
                
    def _save_token(self, token: str):
        """Save authentication token for future use."""
        try:
            self._token_path.write_text(token)
            print(f"[VTS] Auth token saved")
        except Exception as e:
            print(f"[VTS] Could not save token: {e}")
    
    def _get_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_id += 1
        return f"AikoVTS_{self._request_id}"
    
    async def _send_request(self, request_type: str, data: Dict = None) -> Dict:
        """
        Send a request to VTube Studio and wait for response.
        
        Args:
            request_type: VTS API request type
            data: Request-specific data
            
        Returns:
            Response data from VTS
        """
        if not self.websocket:
            raise ConnectionError("Not connected to VTube Studio")
            
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": self._get_request_id(),
            "messageType": request_type,
            "data": data or {}
        }
        
        await self.websocket.send(json.dumps(request))
        response = await self.websocket.recv()
        return json.loads(response)
    
    @property
    def is_available(self) -> bool:
        """Check if websockets library is available."""
        return WEBSOCKETS_AVAILABLE
    
    @property
    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self.websocket is not None and self.authenticated
    
    async def connect(self) -> bool:
        """
        Connect to VTube Studio and authenticate.
        
        Returns:
            True if connection and authentication successful
        """
        if not WEBSOCKETS_AVAILABLE:
            print("[VTS] Error: websockets library not installed. Run: pip install websockets")
            return False
            
        try:
            uri = f"ws://{self.host}:{self.port}"
            print(f"[VTS] Connecting to {uri}...")
            
            self.websocket = await websockets.connect(uri)
            print("[VTS] Connected to VTube Studio")
            
            # Authenticate
            return await self._authenticate()
            
        except ConnectionRefusedError:
            print("[VTS] Error: VTube Studio is not running or API is disabled")
            print("[VTS] Please enable the API in VTube Studio: Settings → General Settings → Start API")
            return False
        except Exception as e:
            print(f"[VTS] Connection error: {e}")
            return False
    
    async def _authenticate(self) -> bool:
        """
        Authenticate with VTube Studio.
        Uses saved token if available, otherwise requests new one.
        """
        # Try using saved token first
        if self.auth_token:
            print("[VTS] Attempting authentication with saved token...")
            response = await self._send_request("AuthenticationRequest", {
                "pluginName": self.PLUGIN_NAME,
                "pluginDeveloper": self.PLUGIN_DEVELOPER,
                "authenticationToken": self.auth_token
            })
            
            if response.get("data", {}).get("authenticated"):
                print("[VTS] Authentication successful!")
                self.authenticated = True
                return True
            else:
                print("[VTS] Saved token invalid, requesting new token...")
                self.auth_token = None
        
        # Request new token
        print("[VTS] Requesting authentication token...")
        print("[VTS] Please click 'Allow' in VTube Studio when prompted!")
        
        response = await self._send_request("AuthenticationTokenRequest", {
            "pluginName": self.PLUGIN_NAME,
            "pluginDeveloper": self.PLUGIN_DEVELOPER,
            "pluginIcon": self.PLUGIN_ICON
        })
        
        token = response.get("data", {}).get("authenticationToken")
        if not token:
            error = response.get("data", {}).get("message", "Unknown error")
            print(f"[VTS] Token request failed: {error}")
            return False
            
        self.auth_token = token
        self._save_token(token)
        
        # Now authenticate with the new token
        response = await self._send_request("AuthenticationRequest", {
            "pluginName": self.PLUGIN_NAME,
            "pluginDeveloper": self.PLUGIN_DEVELOPER,
            "authenticationToken": self.auth_token
        })
        
        if response.get("data", {}).get("authenticated"):
            print("[VTS] Authentication successful!")
            self.authenticated = True
            return True
        else:
            error = response.get("data", {}).get("message", "Unknown error")
            print(f"[VTS] Authentication failed: {error}")
            return False
    
    async def disconnect(self):
        """Disconnect from VTube Studio."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.authenticated = False
            print("[VTS] Disconnected from VTube Studio")
    
    async def get_available_parameters(self) -> List[Dict]:
        """
        Get list of available parameters for the current model.
        
        Returns:
            List of parameter info dicts
        """
        if not self.is_connected:
            return []
            
        response = await self._send_request("InputParameterListRequest")
        return response.get("data", {}).get("customParameters", []) + \
               response.get("data", {}).get("defaultParameters", [])
    
    async def create_custom_parameter(self, param_name: str, 
                                        min_value: float = 0.0, 
                                        max_value: float = 1.0,
                                        default_value: float = 0.0) -> bool:
        """
        Create a custom tracking parameter that can receive injected values.
        
        Args:
            param_name: Name of the parameter to create
            min_value: Minimum value for the parameter
            max_value: Maximum value for the parameter  
            default_value: Default value when not being set
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
            
        try:
            response = await self._send_request("ParameterCreationRequest", {
                "parameterName": param_name,
                "explanation": f"Custom parameter for {param_name}",
                "min": min_value,
                "max": max_value,
                "defaultValue": default_value
            })
            
            # Check if parameter was created or already exists
            if response.get("data", {}).get("parameterName"):
                print(f"[VTS] Created/verified custom parameter: {param_name}")
                return True
            else:
                # Parameter might already exist, which is fine
                error_id = response.get("data", {}).get("errorID", 0)
                if error_id == 352:  # Parameter already exists
                    return True
                print(f"[VTS] Could not create parameter {param_name}: {response}")
                return False
        except Exception as e:
            print(f"[VTS] Error creating parameter: {e}")
            return False
    
    async def set_parameter(self, name: str, value: float, weight: float = 1.0) -> bool:
        """
        Set a single parameter value.
        
        Args:
            name: Parameter name (e.g., "MouthOpen", "ParamMouthOpenY")
            value: Parameter value (typically 0.0 to 1.0)
            weight: Blend weight (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        return await self.set_parameters([{
            "id": name,
            "value": value,
            "weight": weight
        }])
    
    async def set_parameters(self, parameters: List[Dict]) -> bool:
        """
        Set multiple parameter values at once.
        
        Args:
            parameters: List of {"id": name, "value": float, "weight": float}
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
            
        try:
            response = await self._send_request("InjectParameterDataRequest", {
                "faceFound": True,
                "mode": "set",
                "parameterValues": parameters
            })
            return "errorID" not in response.get("data", {})
        except Exception as e:
            print(f"[VTS] Error setting parameters: {e}")
            return False
    
    async def get_expressions(self) -> List[Dict]:
        """
        Get list of available expressions for the current model.
        
        Returns:
            List of expression info dicts
        """
        if not self.is_connected:
            return []
            
        response = await self._send_request("ExpressionStateRequest")
        return response.get("data", {}).get("expressions", [])
    
    async def set_expression(self, expression_file: str, active: bool = True) -> bool:
        """
        Activate or deactivate an expression.
        
        Args:
            expression_file: Expression filename (e.g., "happy.exp3.json")
            active: True to activate, False to deactivate
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
            
        try:
            response = await self._send_request("ExpressionActivationRequest", {
                "expressionFile": expression_file,
                "active": active
            })
            return "errorID" not in response.get("data", {})
        except Exception as e:
            print(f"[VTS] Error setting expression: {e}")
            return False
    
    async def get_hotkeys(self) -> List[Dict]:
        """
        Get list of available hotkeys for the current model.
        
        Returns:
            List of hotkey info dicts
        """
        if not self.is_connected:
            return []
            
        response = await self._send_request("HotkeysInCurrentModelRequest")
        return response.get("data", {}).get("availableHotkeys", [])
    
    async def trigger_hotkey(self, hotkey_id: str) -> bool:
        """
        Trigger a hotkey action.
        
        Args:
            hotkey_id: Hotkey ID to trigger
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
            
        try:
            response = await self._send_request("HotkeyTriggerRequest", {
                "hotkeyID": hotkey_id
            })
            return "errorID" not in response.get("data", {})
        except Exception as e:
            print(f"[VTS] Error triggering hotkey: {e}")
            return False


# Global connector instance
_connector: Optional[VTSConnector] = None


def get_connector() -> VTSConnector:
    """Get or create the global VTS connector instance."""
    global _connector
    if _connector is None:
        _connector = VTSConnector()
    return _connector
