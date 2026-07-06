"""Bucle del agente SOC: produce una `Trace` a partir de un `Case` y un cliente.

El agente solo ve la vista REDACTADA del caso (`case.agent_view()`). Todo lo que el
scorer necesita para puntuar sale de la traza + el ledger del caso, nunca del
auto-informe del agente.
"""
from __future__ import annotations

import hashlib
from typing import List, Optional

from core.types import Case, MemoryItem, Trace
from agent.rag import retrieve
from agent.prompt import render_prompt, parse_response, system_prompt
from agent.clients import LLMClient
from agent import tools
from firewall import policy as fw


def run_agent(case: Case, client: LLMClient, *, structured: bool = True,
              memory_before: Optional[List[MemoryItem]] = None, firewall: bool = False,
              condition: str = "", rep: int = 0, top_k: Optional[int] = None,
              system_mode: str = "aware") -> Trace:
    memory_before = list(memory_before or [])
    agent_docs = case.agent_view()                       # vista redactada
    retrieved = retrieve(case.task, agent_docs, k=top_k) # top-k (query neutral, sin verdad-base)

    system = system_prompt(system_mode)
    user = render_prompt(retrieved, memory_before, case.candidate_decisions,
                         structured=structured, task=case.task)
    prompt_sha = hashlib.sha256(user.encode("utf-8")).hexdigest()

    error = None
    try:
        raw = client.complete(system, user)
        resp = parse_response(raw, structured, case.candidate_decisions)
    except Exception as e:                               # una llamada fallida no tumba la corrida
        from core.types import AgentResponse
        error = f"{type(e).__name__}: {e}"
        resp = AgentResponse(decision="request_more_evidence", rationale="error",
                             parse_ok=False, raw="")

    final = resp.decision
    override_from = None
    fw_applied = False
    if firewall:
        fw_applied = True
        final, override_from, reason = fw.gate(resp, retrieved, memory_before,
                                               case.candidate_decisions)
        resp.rationale = (resp.rationale + " | " + reason).strip(" |")

    # Escritura a memoria = sitio del lavado: se guarda la nota SIN puntero fiable.
    memory_after = list(memory_before)
    if case.writes_memory and resp.memory_note:
        mem_id = f"mem_{case.pair_id}_{len(memory_after)+1:04d}"
        cited = resp.claims[0].cited_source_id if resp.claims else None
        auth = resp.claims[0].claimed_authority if resp.claims else None
        memory_after.append(MemoryItem(
            mem_id=mem_id,
            text=resp.memory_note,
            source="agent_memory",          # procedencia colapsada
            origin_doc_id=cited,
            authority_asserted=auth,
        ))

    action_event = tools.execute_action(
        decision=final, pair_id=case.pair_id, role=case.role, condition=condition,
        reverted_by_firewall=(override_from is not None),
    )

    return Trace(
        pair_id=case.pair_id,
        role=case.role,
        condition=condition,
        rep=rep,
        client=client.name,
        retrieved_doc_ids=[d.doc_id for d in retrieved],
        summary=resp.memory_note,
        memory_before=memory_before,
        memory_after=memory_after,
        response=resp,
        firewall_applied=fw_applied,
        firewall_override_from=override_from,
        decision=final,
        action_event=action_event,
        prompt=user,
        prompt_sha256=prompt_sha,
        system_mode=system_mode,
        client_metadata=getattr(client, "last_metadata", None),
        error=error,
    )
