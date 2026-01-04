import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from mem0.memory.base_supabase import SupabaseManager
from mem0.exceptions import DatabaseError

class Nexus(SupabaseManager):
    """
    Authoritative Sharing Manager for Mem0 Enterprise.
    
    Manages the multi-tier visibility (private, team, global) and the 
    approval flow for promoting memories to higher organizational levels.
    """
    
    def suggest_promotion(self, memory_id: str, suggested_by: str, target: str = 'team') -> None:
        """
        Proposes a memory for promotion to team or organization-wide visibility.
        
        Args:
            memory_id: The UUID of the memory to promote.
            suggested_by: User ID of the person making the suggestion.
            target: The target visibility level ('team' or 'global').
            
        Raises:
            ValueError: If the target visibility is invalid.
            DatabaseError: If the proposal insertion fails.
        """
        if target not in ['team', 'global']:
            raise ValueError("Target visibility must be 'team' or 'global'")
            
        self.logger.info(f"Proposing promotion for memory {memory_id} to {target} by {suggested_by}")
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO memory_proposals (memory_id, suggested_by, target_visibility)
                        VALUES (:memory_id, :suggested_by, :target)
                        ON CONFLICT DO NOTHING
                    """),
                    {"memory_id": memory_id, "suggested_by": suggested_by, "target": target}
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Promotion proposal failed: {str(e)}")
            raise DatabaseError(message=f"Failed to suggest promotion: {str(e)}")

    def list_pending_proposals(self, org_id: str) -> List[Dict[str, Any]]:
        """
        Lists all pending memory proposals for a specific organization.
        
        Args:
            org_id: The ID of the organization to query.
            
        Returns:
            A list of dictionary objects representing pending proposals.
            
        Raises:
            DatabaseError: If the query fails.
        """
        self.logger.debug(f"Listing pending proposals for org_id: {org_id}")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT p.id, p.memory_id, m.metadata->>'data' as content, 
                               p.suggested_by, p.target_visibility
                        FROM memory_proposals p
                        JOIN {self.table_name} m ON p.memory_id = m.id
                        WHERE p.status = 'pending' AND m.org_id = :org_id
                    """),
                    {"org_id": org_id}
                ).fetchall()
                
                return [
                    {
                        "proposal_id": str(row[0]),
                        "memory_id": str(row[1]),
                        "content": row[2],
                        "suggested_by": row[3],
                        "target": row[4]
                    }
                    for row in result
                ]
        except Exception as e:
            raise DatabaseError(message=f"Failed to list proposals: {str(e)}")

    def approve_proposal(self, proposal_id: str, reviewer_id: str, notes: str = "") -> None:
        """
        Approves and promotes a memory proposal. This is an authoritative enterprise action.
        
        Args:
            proposal_id: The UUID of the proposal to approve.
            reviewer_id: User ID of the reviewer/approver.
            notes: Optional justification or summary for the approval.
            
        Raises:
            DatabaseError: If the approval RPC execution fails.
        """
        self.logger.warning(f"Approving proposal {proposal_id} by reviewer {reviewer_id}")
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("SELECT approve_memory_proposal(:pid, :rid, :notes)"),
                    {"pid": proposal_id, "rid": reviewer_id, "notes": notes}
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Approval failed for proposal {proposal_id}: {str(e)}")
            raise DatabaseError(message=f"Failed to approve proposal: {str(e)}")

    def set_agent_context(self, memory_id: str, org_id: str, team_id: Optional[str] = None) -> None:
        """
        Updates the organizational context (tenancy) for a specific memory.
        
        Args:
            memory_id: The UUID of the memory.
            org_id: The new Organization ID.
            team_id: The optional Team ID.
            
        Raises:
            DatabaseError: If the update fails.
        """
        self.logger.info(f"Setting context for memory {memory_id} to org {org_id}")
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text(f"""
                        UPDATE {self.table_name} 
                        SET org_id = :org_id, team_id = :team_id
                        WHERE id = :id
                    """),
                    {"org_id": org_id, "team_id": team_id, "id": memory_id}
                )
                conn.commit()
        except Exception as e:
            raise DatabaseError(message=f"Failed to set agent context: {str(e)}")
