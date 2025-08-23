# backend/services/security_service.py
from typing import Dict, List, Any, Optional, Set
import re
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityThreat:
    threat_type: str
    threat_level: ThreatLevel
    pattern: str
    description: str
    remediation: str

@dataclass
class DetectionResult:
    threats_detected: List[SecurityThreat]
    risk_score: int  # 0-100
    should_block: bool
    metadata: Dict[str, Any]

class SecurityService:
    """Enhanced security service for detecting data exfiltration attempts and other security threats"""
    
    def __init__(self):
        self.threats = self._initialize_threat_patterns()
        self.detection_history: List[Dict] = []
        self.blocked_patterns: Set[str] = set()
        
    def _initialize_threat_patterns(self) -> List[SecurityThreat]:
        """Initialize comprehensive threat detection patterns"""
        return [
            # API Keys and Tokens
            SecurityThreat(
                threat_type="openai_api_key",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"sk-[a-zA-Z0-9]{48}",
                description="OpenAI API key detected",
                remediation="Immediately revoke and regenerate API key. Never share API keys."
            ),
            SecurityThreat(
                threat_type="api_key_mention",
                threat_level=ThreatLevel.HIGH,
                pattern=r"(?i)api\s+key:\s*sk-[a-zA-Z0-9]+",
                description="API key mentioned in message",
                remediation="Remove API keys from messages. Use environment variables or secure vaults."
            ),
            SecurityThreat(
                threat_type="api_key",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9\-\._~\+/]{16,}['\"]?",
                description="API key pattern detected in message",
                remediation="Remove API keys from messages. Use environment variables or secure vaults."
            ),
            SecurityThreat(
                threat_type="bearer_token",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"(?i)authorization:\s*bearer\s+[A-Za-z0-9\-\._~\+/]+=*",
                description="Bearer token detected in message",
                remediation="Remove bearer tokens from messages. Never share authentication tokens."
            ),
            SecurityThreat(
                threat_type="password",
                threat_level=ThreatLevel.HIGH,
                pattern=r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]{4,}['\"]?",
                description="Password pattern detected in message",
                remediation="Remove passwords from messages. Use secure authentication methods."
            ),
            SecurityThreat(
                threat_type="secret",
                threat_level=ThreatLevel.HIGH,
                pattern=r"(?i)secret\s*[:=]\s*['\"]?[a-zA-Z0-9\-\._~\+/]{8,}['\"]?",
                description="Secret value detected in message",
                remediation="Remove secrets from messages. Use secure secret management."
            ),
            SecurityThreat(
                threat_type="aws_access_key",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"AKIA[0-9A-Z]{16}",
                description="AWS Access Key ID detected",
                remediation="Immediately rotate AWS keys and use IAM roles or temporary credentials."
            ),
            SecurityThreat(
                threat_type="jwt_token",
                threat_level=ThreatLevel.HIGH,
                pattern=r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*",
                description="JWT token detected",
                remediation="Remove JWT tokens from messages. Tokens should never be shared."
            ),
            SecurityThreat(
                threat_type="private_key",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
                description="Private key detected",
                remediation="Immediately revoke and regenerate private keys. Never share private keys."
            ),
            SecurityThreat(
                threat_type="database_connection",
                threat_level=ThreatLevel.HIGH,
                pattern=r"(mongodb|mysql|postgresql|redis)://[^\\s]+",
                description="Database connection string detected",
                remediation="Remove database URLs. Use connection pooling and environment variables."
            ),
            SecurityThreat(
                threat_type="internal_ip",
                threat_level=ThreatLevel.MEDIUM,
                pattern=r"\b(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
                description="Internal IP address detected",
                remediation="Avoid sharing internal network topology. Use generic references."
            ),
            SecurityThreat(
                threat_type="email_credential",
                threat_level=ThreatLevel.MEDIUM,
                pattern=r"(?i)(user|email)\s*[:=]\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                description="Email credential pattern detected",
                remediation="Avoid sharing email credentials. Use secure authentication flows."
            ),
            SecurityThreat(
                threat_type="credit_card",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
                description="Potential credit card number detected",
                remediation="Never share payment information. Use tokenized payment systems."
            ),
            SecurityThreat(
                threat_type="social_security",
                threat_level=ThreatLevel.CRITICAL,
                pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                description="Potential SSN detected",
                remediation="Never share personal identification numbers."
            )
        ]
    
    def detect_threats(self, messages: List[Dict], conversation_id: str = None) -> DetectionResult:
        """Detect security threats in chat messages with enhanced analysis"""
        with tracer.start_as_current_span(
            "security.threat_detection",
            attributes={
                "security.conversation_id": conversation_id or "unknown",
                "security.message_count": len(messages)
            }
        ) as span:
            detected_threats = []
            risk_score = 0
            metadata = {
                "detection_timestamp": datetime.utcnow().isoformat(),
                "conversation_id": conversation_id,
                "total_messages_analyzed": len(messages)
            }
            
            try:
                for i, message in enumerate(messages):
                    message_content = self._extract_message_content(message)
                    if not message_content:
                        continue
                    
                    # Analyze each message for threats
                    message_threats = self._analyze_message(message_content, i)
                    detected_threats.extend(message_threats)
                
                # Calculate risk score based on detected threats
                risk_score = self._calculate_risk_score(detected_threats)
                
                # Determine if we should block the request
                should_block = self._should_block_request(detected_threats, risk_score)
                
                # Update span attributes
                span.set_attributes({
                    "security.threats_detected": len(detected_threats),
                    "security.risk_score": risk_score,
                    "security.should_block": should_block,
                    "security.threat_types": [t.threat_type for t in detected_threats]
                })
                
                # Log security event
                if detected_threats:
                    self._log_security_event(detected_threats, risk_score, conversation_id)
                
                # Store detection history for analysis
                self._store_detection_event(detected_threats, risk_score, metadata)
                
                span.set_status(StatusCode.OK)
                
                return DetectionResult(
                    threats_detected=detected_threats,
                    risk_score=risk_score,
                    should_block=should_block,
                    metadata=metadata
                )
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(f"Error in threat detection: {e}")
                
                # Return safe default on error
                return DetectionResult(
                    threats_detected=[],
                    risk_score=0,
                    should_block=False,
                    metadata={"error": str(e)}
                )
    
    def _extract_message_content(self, message: Dict) -> str:
        """Extract text content from various message formats"""
        if isinstance(message, dict):
            content = message.get('content', '')
        else:
            content = str(message)
        
        if isinstance(content, str):
            return content
        elif isinstance(content, (dict, list)):
            return json.dumps(content)
        else:
            return str(content)
    
    def _analyze_message(self, content: str, message_index: int) -> List[SecurityThreat]:
        """Analyze a single message for security threats"""
        detected_threats = []
        
        for threat in self.threats:
            try:
                pattern = re.compile(threat.pattern)
                matches = pattern.finditer(content)
                
                for match in matches:
                    # Create a copy of the threat with match-specific info
                    threat_instance = SecurityThreat(
                        threat_type=threat.threat_type,
                        threat_level=threat.threat_level,
                        pattern=threat.pattern,
                        description=f"{threat.description} (Message {message_index + 1})",
                        remediation=threat.remediation
                    )
                    detected_threats.append(threat_instance)
                    
            except re.error as e:
                logger.warning(f"Invalid regex pattern for {threat.threat_type}: {e}")
                continue
        
        return detected_threats
    
    def _calculate_risk_score(self, threats: List[SecurityThreat]) -> int:
        """Calculate overall risk score based on detected threats"""
        if not threats:
            return 0
        
        score_map = {
            ThreatLevel.LOW: 10,
            ThreatLevel.MEDIUM: 25,
            ThreatLevel.HIGH: 50,
            ThreatLevel.CRITICAL: 75
        }
        
        total_score = sum(score_map[threat.threat_level] for threat in threats)
        
        # Apply multiplier for multiple threats
        if len(threats) > 1:
            multiplier = min(1.5, 1 + (len(threats) - 1) * 0.1)
            total_score = int(total_score * multiplier)
        
        return min(100, total_score)
    
    def _should_block_request(self, threats: List[SecurityThreat], risk_score: int) -> bool:
        """Determine if request should be blocked based on threats and policy"""
        # Block on critical threats or high risk score
        critical_threats = [t for t in threats if t.threat_level == ThreatLevel.CRITICAL]
        
        return len(critical_threats) > 0 or risk_score >= 75
    
    def _log_security_event(self, threats: List[SecurityThreat], risk_score: int, conversation_id: str):
        """Log security events for monitoring and alerting"""
        threat_summary = {
            threat.threat_level.value: len([t for t in threats if t.threat_level == threat.threat_level])
            for threat in threats
        }
        
        logger.warning(
            f"Security threats detected - Risk Score: {risk_score}, "
            f"Conversation: {conversation_id}, Threats: {threat_summary}"
        )
        
        # Add structured event for external monitoring
        for threat in threats:
            logger.warning(
                f"SECURITY_THREAT: {threat.threat_type} | Level: {threat.threat_level.value} | "
                f"Description: {threat.description}"
            )
    
    def _store_detection_event(self, threats: List[SecurityThreat], risk_score: int, metadata: Dict):
        """Store detection event for historical analysis"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "threats": [
                {
                    "type": t.threat_type,
                    "level": t.threat_level.value,
                    "description": t.description
                } for t in threats
            ],
            "risk_score": risk_score,
            "metadata": metadata
        }
        
        # Keep last 1000 events in memory for analysis
        self.detection_history.append(event)
        if len(self.detection_history) > 1000:
            self.detection_history.pop(0)
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get statistics about recent threat detections"""
        if not self.detection_history:
            return {"total_events": 0}
        
        recent_events = [
            e for e in self.detection_history
            if datetime.fromisoformat(e["timestamp"]) > datetime.utcnow() - timedelta(hours=24)
        ]
        
        threat_types = {}
        for event in recent_events:
            for threat in event["threats"]:
                threat_type = threat["type"]
                threat_types[threat_type] = threat_types.get(threat_type, 0) + 1
        
        return {
            "total_events": len(self.detection_history),
            "recent_24h_events": len(recent_events),
            "avg_risk_score": sum(e["risk_score"] for e in recent_events) / max(len(recent_events), 1),
            "top_threat_types": sorted(threat_types.items(), key=lambda x: x[1], reverse=True)[:5]
        }
