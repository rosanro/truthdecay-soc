# TruthDecay-SOC — andamiaje del MVP

Prototipo del proyecto *TruthDecay-SOC*. Mide, de forma **causal** y con
un **scorer determinista independiente del auto-informe del agente**, si un *claim*
falso con procedencia aparente puede (1) cambiar una decisión de un agente SOC,
(2) escribirse en su memoria perdiendo la procedencia (lavado) y (3) **seguir
controlando decisiones tras borrar la fuente original** (persistencia). Y si un
*Epistemic Firewall* lo contiene.

> El malware del mundo *agentic* puede no ser código, sino una creencia falsa con
> suficiente procedencia aparente para cambiar una acción.

## Diseño causal y controles

El andamiaje anterior decidía con `if veneno: return comprometido`: cableaba el
resultado. Aquí no. Dos garantías, ambas ejecutables como test:

1. **Frontera agente/ledger.** El agente solo ve una vista *redactada*
   (`doc_id`, `source_type`, `content`). Nunca ve la autoridad numérica, `is_canonical`
   ni si el documento porta el claim falso. Verificado en `tests/test_redaction.py`
   (la vista del agente ni siquiera *expone* esos atributos, y es inmutable).
2. **Scorer desde el ledger, no desde el auto-informe.** Las métricas primarias
   (TFCA, ASR, DDR, AIR, PCR) se reconstruyen desde la verdad-base del caso y la traza.
   El auto-informe del agente solo alimenta PRE (secundaria). Verificado con valores
   exactos en `tests/test_scorer_golden.py`.

El compromiso **emerge** de un agente que razona sobre contenido, y la causalidad se
establece por **contrafactual but-for** (quitar el veneno y ver si deja de fallar),
no por una etiqueta.

## Ejecutar (sin instalar nada)

```bash
python demo.py                          # mock:credulous — determinista, sin red (caso c2_01)
python demo.py --case p1_01             # familia phishing        (mismo harness)
python demo.py --case v1_01             # familia vulnerabilidades (mismo harness)
python demo.py --case s1_01             # familia supply chain     (mismo harness)
python demo.py --case c3_01             # 'veneno sutil': C2 con provenance falsa plausible
python demo.py --client mock:skeptical  # agente que no se deja engañar (control)
python demo.py --system-mode neutral    # sensibilidad: sin instrucción de autoridad en el prompt
python demo.py --top-k 2                 # presión RAG: recuperar solo 2 documentos
python dashboard/render_static.py --pair c2_01   # dashboard HTML (fuente→claim→memoria→acción)
python -m unittest discover -s tests    # 30 tests (scorer, causal, redacción, e2e, costura LLM, pipeline, validación, forense)
```


**Resultados empíricos:** ver [`docs/RESULTS.md`](docs/RESULTS.md) (un positivo de una sola pasada `c2_01` y un hallazgo de memoria temporal `t2_01` sobre `gemini-2.5-flash-lite`: matriz completa y lectura de límites). Variante temporal de memoria (fase 2, experimental): `python -m experiments.run_campaign --campaign cases/campaigns/t2_01.json --client gemini:gemini-2.5-flash-lite --system-mode neutral --reps 3 --out results/t2_neutral` (protocolo en `docs/GEMINI.md`).

La demo imprime la cadena `C0 → C3 → C7 → C7-control → C5`, la tabla de métricas
(desde el ledger) y el veredicto causal por hipótesis.

## Conectar un LLM real (Gemini u OpenAI-compatible)

El harness es agnóstico de proveedor: el mismo prompt y el mismo parser sirven para el
mock y para un LLM real. Solo cambia el cliente.

```bash
pip install -e ".[gemini]"           # core + SDK de Gemini
export GEMINI_API_KEY=...            # o GOOGLE_API_KEY
python demo.py --client gemini --reps 3
```

```bash
pip install -e ".[openai]"           # OpenAI, vLLM, Ollama, Together...
export OPENAI_API_KEY=...            # OPENAI_BASE_URL opcional
python demo.py --client openai:gpt-4o-mini --reps 3
```

También hay cliente `anthropic` (`pip install -e ".[anthropic]"`, `ANTHROPIC_API_KEY`).

**Modelo Gemini:** por defecto `gemini-2.5-flash` (estable, GA y barato). Para otros
modelos consulta la lista vigente en `ai.google.dev/gemini-api/docs/models` y fija uno
concreto con `--client gemini:MODELO`. El cliente añade `response_schema` (con *fallback*
si el modelo lo rechaza), reintentos con backoff y captura de metadata (tokens, latencia).

**Coste de una corrida:** la historia de un caso son 7 llamadas (`--reps 1`) o 21
(`--reps 3`), cada una de ~500 tokens. En `gemini-2.5-flash` son céntimos.

La costura está verificada sin red en `tests/test_llm_seam.py`: el objeto
`GeminiClient` real recorre toda la historia con solo el salto de red falseado (tolera
vallas ```json y *thought parts* de 2.5+). Con el mock, las tasas son 0/1 por
construcción: **el mock es un *fixture* que valida la tubería y el scorer, no un
estimador de la tasa del modelo real**.

## Pipeline de resultados (tabla experimental)

```bash
python run_grid.py                                   # mock (fixture), todos los pares
python run_grid.py --client gemini --reps 3          # LLM real
python run_grid.py --client gemini --save-traces --dashboards   # + trazas forenses + dashboards
```

Genera, por cliente: `results_<c>.csv` (una fila por par×condición), `summary_<c>.csv`
(agregado por condición con **IC bootstrap al 95%, unidad = caso**) y
`manifest_<c>.json` (reproducibilidad: modelo, SDK, timestamp, git, config).
Con `--save-traces` añade **`traces_<c>.jsonl`**: una línea por llamada con prompt
renderizado + `prompt_sha256`, `raw` response, `parse_ok`, decisión, claims, memoria,
docs recuperados, override del firewall, `action_event` y metadata (tokens/latencia).
Esto es lo que hace **auditable llamada por llamada** la primera corrida real de Gemini.
Con `--dashboards` emite un `dashboard_<pair>.html` por par.

## Cobertura de métricas

Qué se mide **hoy** desde la traza + el ledger (el SDK del LLM solo aporta la salida del
modelo; todo lo demás lo reconstruye el scorer):

| Métrica | Estado | Fuente |
|---|---|---|
| ASR, DDR, TFCA, AIR, PCR | implementada | decisión + ledger |
| parse_ok_rate, poison/canonical_retrieved_rate | implementada | validez de la corrida (esencial con LLM real) |
| PPR (persistencia) | implementada | seed/probe/contrafactual |
| SLR, CLR, PRE (secundarias) | implementada | nota/resumen + auto-informe vs ledger |
| Atribución causal but-for | implementada | mayoría sobre repeticiones |
| Defensa: H-D1a contiene / **H-D1b corrige** / C5 abstain_rate | implementada | distingue contención de abstención |
| C6 coste limpio en seed **y probe** | implementada | utilidad del firewall en ambos limpios |
| IC bootstrap (unidad=caso) | implementada | `run_grid.py` |
| THL (saltos de transformación) | **cualitativa** en MVP | en qué etapa se pierde la verdad |
| H-D′ ablación 3 brazos del firewall | **planificada** (escalado) | puerta canónica / no-override / cuarentena por separado |
| H-E curva de erosión (Kaplan-Meier) | **planificada** (exploratoria) | reusa datos E2/E3 |
| H-G detector sin ledger (AUC-ROC) | **planificada** (exploratoria) | PRE-interno como clasificador |

Las primarias y las secundarias principales están cerradas; el *tier* exploratorio
(H-D′/H-E/H-G) queda declarado como trabajo del escalado, coherente con el Anexo B.

## El mock es un fixture, no evidencia

El mock **no es evidencia empírica sobre modelos frontera**; es un *fixture de
integración* que demuestra que el harness, el scorer, los contrafactuales y el firewall
funcionan de extremo a extremo. La evidencia empírica se obtiene con Gemini durante el
desarrollo. Con el mock, las tasas son 0/1 por construcción.

**Sobre los marcadores léxicos (`core/markers.py`).** Se usan en tres sitios con
papeles distintos, que conviene no confundir:
- en el **mock**, son el mecanismo del *fixture* (cómo decide la persona simulada);
- en el **firewall**, son un proxy barato de soporte/contradicción por fuente (en
  producción sería un modelo NLI o el propio LLM);
- en el **scorer**, la verdad se toma del *ledger* y de `false_claim_markers` del caso.

Con un LLM real el mock desaparece: la decisión viene del modelo, y los marcadores solo
afectan a firewall y scorer. La coincidencia léxica mock↔firewall solo existe en las
corridas mock+firewall, que son explícitamente fixtures.

## Arquitectura

```
core/        types (frontera agente/ledger), decisiones, marcadores léxicos
cases/       pares seed/probe en JSON (9 pares: 6 categorías SOC, 8 etiquetas técnicas + 2 campañas) + loader + validate
agent/       rag (BM25-lite) · memory (JSONL) · prompt · clients · tools (sandbox) · loop
firewall/    Epistemic Firewall: tipado por source_type, cuarentena de memoria, política acción→autoridad
scorer/      ledger · metrics (TFCA/ASR/DDR/AIR/PCR/SLR/CLR/PRE) · causal (but-for) · bootstrap
experiments/ conditions (C0/C1/C3/C7/C5/C6) · run (historia E3 + contrafactuales + PPR + veredicto)
dashboard/   render_static (HTML autocontenido: fuente→claim→memoria→acción)
tests/       redacción · scorer golden · causal · e2e ×3 · costura LLM · pipeline · validación
demo.py      ·  run_grid.py  ·  docs/DEMO.md  ·  results/example/ (artefactos de ejemplo)
```

## Mapa a las hipótesis de la memoria

| Hipótesis | Qué comprueba | Dónde |
|---|---|---|
| H-A | el claim falso cambia la decisión (efecto inmediato, atribuible) | C3 vs C0, `causal.attack_attributable` |
| H-B | el claim se escribe en memoria perdiendo procedencia (lavado) | `ledger.laundering_succeeded`, SLR |
| H-C | persiste tras borrar la fuente (solo vía memoria) | C7 vs contrafactual, `persistence_attributable`, PPR |
| H-C′ | el fallo es del *contenido* falso, no de la mera memoria | **C7-control** (memoria benigna) |
| H-D | el Epistemic Firewall contiene el ataque sin romper utilidad | C5 (atacado) y C6 (limpio) |
| PRE/H-G | discrepancia procedencia declarada vs real; base del detector runtime | métrica PRE |

## Añadir un caso

Crea `cases/<pair>_seed.json` y `cases/<pair>_probe.json` con: `documents`
(cada uno con `source_type`, `authority`, `is_canonical`, `supports_decision`, y
`carries_false_claim` en el veneno), `candidate_decisions`, `correct_decision`,
`attacker_target_decision` y `false_claim_markers` (la *firma* del claim falso, p. ej.
la reasegurancia, **no** el nombre del activo). El resto del harness no cambia.

## Alcance y límites

Con N pequeño (5–10 pares), la afirmación primaria es de **existencia y atribución
causal**, no de tasa precisa; los IC serían anchos (ver §8 de la memoria). Un resultado
**negativo bien atribuido** (p. ej. efecto inmediato sí, persistencia no) también es un
resultado válido. La autoridad de las fuentes aquí se asigna por diseño; inferirla
automáticamente en un SOC real es el trabajo siguiente, no parte de este MVP.
