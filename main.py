import json
import time
import base64
import concurrent.futures
import re
import os
import tempfile
import uuid
from typing import List
import asyncio

from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models import Meeting, Expert, Project, FileData, FileReference, PolicyRequest
from utils import load_projects, save_projects, load_templates, save_templates

from ingestion import process_documents
from retrieval import retrieve_documents
from think_tank import ThinkTank
from agent_builder import build_local_agent
from utils import clean_name, export_meeting
from agno.memory.v2 import UserMemory

app = FastAPI()

# Allow CORS for your frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# In-memory caches (backed by JSON files)
projects_db = load_projects()
TEMPLATES = load_templates()

# File storage for uploaded PDFs
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
file_storage = {}  # Maps session_id -> {expert_name: [(filename, file_path), ...]}

def clean_think_tags(text: str) -> str:
    """
    Cleans the text by removing '<think>...</think>' tags and their content.
    
    Args:
        text (str): The input text to clean.
        
    Returns:
        str: The cleaned text without think tags and their content.
    """
    # Use regex to remove <think>...</think> tags and everything inside them
    # The pattern uses non-greedy matching (.*?) to avoid matching across multiple think blocks
    # The re.DOTALL flag allows . to match newlines as well
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up extra whitespace that might be left behind
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Replace multiple consecutive whitespace with single space
    cleaned_text = cleaned_text.strip()  # Remove leading/trailing whitespace
    
    return cleaned_text

@app.get("/projects")
async def list_projects():
    obj = projects_db
    print(obj)
    return obj


@app.post("/projects")
async def create_project(tpl: Project):
    if tpl.title in projects_db:
        raise HTTPException(400, "Project already exists")
    projects_db[tpl.title] = tpl.serialize()
    save_projects(projects_db)
    return {"msg": "created"}


@app.get("/projects/{name}")
async def get_project(name: str):
    if name not in projects_db:
        raise HTTPException(404, "Not found")
    return projects_db[name]

@app.get("/templates")
async def get_templates():
    return TEMPLATES


@app.post("/templates")
async def upsert_template(tpl: Expert):
    global TEMPLATES
    # remove existing with same title
    TEMPLATES = [t for t in TEMPLATES if t["title"] != tpl.title]
    TEMPLATES.append(tpl.dict())
    save_templates(TEMPLATES)
    return {"msg": "saved"}

@app.delete("/templates/{title}")
async def del_template(title: str):
    global TEMPLATES
    TEMPLATES = [t for t in TEMPLATES if t["title"] != title]
    save_templates(TEMPLATES)
    return {"msg": "deleted"}


@app.post("/upload-files/{session_id}/{expert_name}")
async def upload_files(session_id: str, expert_name: str, files: List[UploadFile] = File(...)):
    """
    Upload PDF files for a specific expert in a meeting session.
    Returns file references that can be used in the WebSocket meeting.
    """
    try:
        if session_id not in file_storage:
            file_storage[session_id] = {}
        
        if expert_name not in file_storage[session_id]:
            file_storage[session_id][expert_name] = []
        
        uploaded_files = []
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(400, f"Only PDF files are allowed. Got: {file.filename}")
            
            # Generate unique filename to avoid conflicts
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            # Save file to disk
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Store file reference
            file_storage[session_id][expert_name].append((file.filename, file_path))
            uploaded_files.append({
                "original_name": file.filename,
                "size": len(content)
            })
        
        return {
            "session_id": session_id,
            "expert_name": expert_name,
            "files": uploaded_files,
            "message": f"Successfully uploaded {len(files)} files"
        }
    
    except Exception as e:
        raise HTTPException(500, f"File upload failed: {str(e)}")

@app.delete("/files/{session_id}")
async def cleanup_session_files(session_id: str):
    """Clean up files for a session"""
    if session_id in file_storage:
        # Delete physical files
        for expert_files in file_storage[session_id].values():
            for _, file_path in expert_files:
                try:
                    os.remove(file_path)
                except OSError:
                    pass  # File might already be deleted
        
        # Remove from storage
        del file_storage[session_id]
        return {"message": "Session files cleaned up"}
    
    return {"message": "Session not found"}

@app.websocket("/ws/meeting")
async def meeting_ws(websocket: WebSocket):
    """
    Client must first send a JSON payload with the Meeting fields:
    {
      "project_name": str,
      "experts": [ {title, expertise, goal, role}, ... ],
      "vector_store": [[{filename: str, content: str}, ...]],  # optional, if files are uploaded
      "meeting_topic": str,
      "rounds": int
    }
    Where vector_store contains arrays of file objects with base64-encoded content.
    Then the server will stream every log line as JSON messages:
    { "name": <agent_name>, "content": <text> }
    """
    print(f"WebSocket connection attempt from: {websocket.client}")
    await websocket.accept()
    print("WebSocket connection accepted successfully!")
    
    # Add a small delay to ensure connection is fully established
    await asyncio.sleep(0.1)
    
    try:
        print("Waiting for initial JSON payload...")
        # Add a timeout to the receive operation
        init = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
        print(f"Received JSON payload with keys: {list(init.keys())}")
        
        # Check payload size
        vector_store = init.get('vector_store', [])
        total_files = sum(len(expert_files) for expert_files in vector_store)
        print(f"Total files to process: {total_files}")
        
        if total_files > 0:
            # Estimate payload size
            total_size = 0
            for expert_files in vector_store:
                for file_data in expert_files:
                    if isinstance(file_data, dict) and 'content' in file_data:
                        total_size += len(file_data['content'])
            print(f"Estimated payload size: {total_size / (1024*1024):.2f} MB")
        
        # Add optional fields if missing
        init['timestamp'] = int(time.time())
        init['transcript'] = []
        init['summary'] = ""
        
        # Validate the Meeting model
        print("Creating Meeting model...")
        req = Meeting(**init)
        print("Meeting model created successfully!")
        
        # Debug: Print what we received
        print(f"Session ID: {getattr(req, 'session_id', 'None')}")
        print(f"File references: {getattr(req, 'file_references', 'None')}")
        print(f"Vector store: {getattr(req, 'vector_store', 'None')}")
        print(f"File storage keys: {list(file_storage.keys())}")
        if req.session_id and req.session_id in file_storage:
            print(f"Files in session {req.session_id}: {file_storage[req.session_id]}")
        
    except asyncio.TimeoutError:
        print("Timeout waiting for initial JSON payload")
        try:
            await websocket.send_json({"name": "error", "content": "Timeout waiting for initial data"})
        except:
            pass
        await websocket.close(code=1008)
        return
    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected during initialization: {e}")
        return  # Don't try to send anything to a disconnected socket
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        try:
            await websocket.send_json({"name": "error", "content": f"Invalid JSON format: {e}"})
        except:
            pass  # Socket might already be closed
        await websocket.close(code=1003)
        return
    except ValueError as e:
        print(f"Meeting model validation error: {e}")
        try:
            await websocket.send_json({"name": "error", "content": f"Invalid meeting data: {e}"})
        except:
            pass  # Socket might already be closed
        await websocket.close(code=1003)
        return
    except Exception as e:
        print(f"Unexpected error parsing init JSON or Meeting model: {e}")
        print(f"Error type: {type(e)}")
        try:
            await websocket.send_json({"name": "error", "content": f"Server error: {e}"})
        except:
            pass  # Socket might already be closed
        await websocket.close(code=1003)
        return
    
    transcript = []
    
    # Initialize lab early to avoid NameError in stream function
    project_desc = projects_db.get(req.project_name, {}).get("description", "")
    lab = ThinkTank(project_desc)

    # helper to stream and log
    async def stream(name: str, content: str, round = None):
        """Helper to send a message and log it."""
        transcript.append({"name": name, "content": content, "round": round})
        try:
            print(f"Attempting to stream: {name}")
            await websocket.send_json({"name": name, "content": content, "round": round})
            print(f"Successfully streamed: {name}")
            lab._log("stream", name, content)
        except Exception as e:
            print(f"!!!!!! FAILED to send stream message for '{name}'. Error: {e} !!!!!!")
    # 1) ingest documents in parallel
    await stream("System", "Starting document ingestion...")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for i, sci in enumerate(req.experts):
            # Handle both new file reference system and legacy base64 system
            file_bytes_list = []
            
            # New system: file references
            if req.session_id and req.session_id in file_storage:
                expert_files = file_storage[req.session_id].get(sci.title, [])
                print(f"Found {len(expert_files)} files for expert {sci.title} in session {req.session_id}")
                for original_name, file_path in expert_files:
                    try:
                        with open(file_path, 'rb') as f:
                            pdf_bytes = f.read()
                        file_bytes_list.append((original_name, pdf_bytes))
                        print(f"Loaded file from disk: {original_name} ({len(pdf_bytes)} bytes)")
                    except Exception as e:
                        error_msg = f"Error loading file {original_name}: {e}"
                        print(error_msg)
                        await websocket.send_json({"name": "ingestion", "content": error_msg})
                        continue
            
            # Legacy system: base64 files (fallback)
            elif hasattr(req, 'vector_store') and req.vector_store and i < len(req.vector_store):
                file_data_list = req.vector_store[i]
                print(f"Processing {len(file_data_list)} base64 files for expert {sci.title}")
                for file_data in file_data_list:
                    try:
                        # Decode base64 content to bytes
                        pdf_bytes = base64.b64decode(file_data.content)
                        file_bytes_list.append((file_data.filename, pdf_bytes))
                        print(f"Successfully decoded file: {file_data.filename} ({len(pdf_bytes)} bytes)")
                    except Exception as e:
                        error_msg = f"Error decoding file {file_data.filename}: {e}"
                        print(error_msg)
                        await websocket.send_json({"name": "ingestion", "content": error_msg})
                        continue
            else:
                print(f"No files found for expert {sci.title}")

            if file_bytes_list:
                print(f"Submitting {len(file_bytes_list)} files for processing for expert: {sci.title}")
                futures.append(executor.submit(process_documents, file_bytes_list, clean_name(sci.title)))
            else:
                print(f"No files to process for expert: {sci.title}")
            
        # Wait for all document processing to complete
        if futures:
            await stream("System", f"Processing {len(futures)} document collections...")
            for f in concurrent.futures.as_completed(futures):
                try:
                    f.result()
                    print("Document processing completed successfully")
                except Exception as e:
                    error_msg = f"Document processing error: {e}"
                    print(error_msg)
                    await websocket.send_json({"name": "ingestion", "content": error_msg})
        else:
            print("No document collections to process")
        
    await stream("System", "Document ingestion completed!")
    
    # Ensure we have a valid project description
    if req.project_name not in projects_db:
        error_msg = f"Project '{req.project_name}' not found"
        print(error_msg)
        await websocket.send_json({"name": "error", "content": error_msg})
        await websocket.close(code=1003)
        return
        
    # Update lab with the correct project description
    lab = ThinkTank(project_desc)
    lab.scientists.clear()
    tools = [retrieve_documents]
    for sd in req.experts:            lab.scientists.append(
            build_local_agent(
                name=sd.title,
                description=f"Expertise: {sd.expertise}. Goal: {sd.goal}",
                role=sd.role,
                memory=None,
                storage=lab._storage,
                tools=tools,
            )
        )
    print('Starting meeting for project:', req.project_name)
    await stream(f"Starting meeting for project: {req.project_name}", "")
    await asyncio.sleep(0.01)
    # transcript.append({"heading": f"🧑‍🔬 Team Meeting - {req.meeting_topic}"})
    await stream('# 🧑‍🔬 Team Meeting', f'## {req.meeting_topic}')
    await asyncio.sleep(0.01)

    # PI opening
    pi_open = lab.pi.run(
        f"You are convening a team meeting. Agenda: {req.meeting_topic}. Share initial guidance to the experts..",
        stream=False,
    ).content
    await stream(lab.pi.name, clean_think_tags(pi_open), round=0)
    await asyncio.sleep(0.01)
    # discussion rounds
    for r in range(1, req.rounds + 1):
        await stream(f"## Round {r}/{req.rounds}", "")
        await asyncio.sleep(0.01)
        # transcript.append({"subheading": f"Round {r}/{req.rounds}"})
        for sci in lab.scientists:
            tool_prompt = f"""
                You are an expert in a team meeting. Your task is to contribute to the discussion based on your expertise and the context provided.
                Title: {sci.name}
                Description: {sci.description}
                Role: {sci.role}
                Context so far:\n{lab._context()}\n\n
                DO NOT summarize or paraphrase the context, but use it to inform your response.
                Generate a new response every time.

                You have access to the following tool:

                1.Tool: `retrieve_documents`
                    - Purpose: Retrieve relevant document chunks from the knowledge database using natural language queries.
                    - Usage:
                        1. Analyze the current task or context and formulate meaningful queries.
                        2. Call: retrieve_documents(queries: List[str], collection_name: str) -> List[str]
                        3. Use collection_name = {clean_name(sci.name)}

                    Instructions:
                    - First, think about what information is needed to accomplish your task.
                    - Generate targeted, specific queries based on your expertise.
                    - Use `retrieve_documents` to fetch supporting content.
                    - Incorporate retrieved content directly into your reasoning or task output.
                    - **Do not output the summary or paraphrase the retrieved content — use it as-is.**

                Your goal is to leverage the retrieved knowledge to solve the task accurately and completely.

                The meeting until now: 
                {lab._context()}
            """
            resp = sci.run(tool_prompt, stream=False).content
            print(f"Expert {sci.name} response: {resp}")
            resp = clean_think_tags(resp)
            await stream(f'{sci.name}', resp, round = r)
            await asyncio.sleep(0.01)
            # transcript.append({"name": sci.name, "content": resp})
        
        crit = lab.critic.run(f"Context so far:\n{lab._context()}\nCritique round {r}", stream=False).content
        crit = clean_think_tags(crit)
        await stream(lab.critic.name, crit, round=r)
        await asyncio.sleep(0.01)
        # transcript.append({"name": lab.critic.name, "content": crit})

        synth = lab.pi.run(f"Context so far:\n{lab._context()}\nSynthesise round {r} and pose follow-ups.", stream=False).content
        synth = clean_think_tags(synth)
        await stream(f"{lab.pi.name} (Feedback)", synth, round=r)
        await asyncio.sleep(0.01)
        # transcript.append({"name": f"{lab.pi.name} (Feedback)", "content": synth})

    # final summary
    summary = lab.pi.run(f"Context so far:\n{lab._context()}\nProvide the final detailed meeting summary and recommendations.", stream=False).content
    summary = clean_think_tags(summary)
    await stream("** FINAL SUMMARY **", summary)
    await asyncio.sleep(0.01)
        # transcript.append({"name": "FINAL SUMMARY", "content": summary})

        # persist memory & save project
    # Memory is now handled automatically by the agent's storage
    # lab._memory.add_user_memory(memory=UserMemory(memory=summary), user_id=req.project_name)
    proj = projects_db.setdefault(req.project_name, {
        "title": req.project_name,
        "description": project_desc,
        "meetings": []
    })
    proj["description"] = project_desc
    proj["meetings"].append({
        "project_name": req.project_name,
        "experts": [s.dict() for s in req.experts],
        "vector_store": [],
        "meeting_topic": req.meeting_topic,
        "rounds": req.rounds,
        "timestamp": int(time.time()),
        "transcript": transcript,
        "summary": summary,
    })
    save_projects(projects_db)

    # signal end
    await websocket.send_json({"name": "__end__", "content": "Meeting complete"})
    await asyncio.sleep(0.01)
    await websocket.close()


# ── Policy Analysis WebSocket ──────────────────────────────────────────────────

@app.websocket("/ws/policy")
async def policy_ws(websocket: WebSocket):
    """Stream the policy analysis pipeline to the frontend.

    Expects: { "query": str }
    Streams:  { "name": str, "content": str } messages, ending with __end__.
    """
    await websocket.accept()

    try:
        init = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
    except asyncio.TimeoutError:
        await websocket.close(code=1008)
        return
    except Exception as e:
        await websocket.close(code=1003)
        return

    query = (init.get("query") or "").strip()
    if not query:
        await websocket.send_json({"name": "error", "content": "No query provided."})
        await websocket.close()
        return

    async def send(name: str, content: str) -> None:
        try:
            await websocket.send_json({"name": name, "content": content})
        except Exception:
            pass

    # ── Import node functions lazily so startup stays fast ──────────────────
    from orchestrator import (
        node_plan_policy,
        node_research,
        node_stakeholder_research,
        node_synthesize,
        node_recommend,
        node_forecast,
        node_finalize,
        _build_result,
    )

    # Build a minimal PolicyRequest from the free-text query
    request = PolicyRequest(
        question=query,
        geography="general",
        objective=f"Analyze and provide a policy recommendation for: {query}",
    )

    state = {
        "run_id": uuid.uuid4().hex[:12],
        "request": request,
        "model_events": [],
        "events": [],
    }

    loop = asyncio.get_event_loop()

    # Each tuple: (ws_name_prefix, node_fn, human_label)
    pipeline = [
        ("plan_policy",           node_plan_policy,           "Policy Director planning…"),
        ("node_research",         node_research,              "Research agent gathering evidence…"),
        ("stakeholder",           node_stakeholder_research,  "Stakeholder analysis in progress…"),
        ("synthesize_research",   node_synthesize,            "Synthesizing findings…"),
        ("implement",             node_recommend,             "Building recommendation…"),
        ("run_forecast",          node_forecast,              "Running deterministic forecast…"),
        ("finalize_result",       node_finalize,              "Finalizing briefing…"),
    ]

    for ws_name, node_fn, label in pipeline:
        await send(ws_name, label)
        try:
            state = await loop.run_in_executor(None, node_fn, state)
            # Forward the latest activity log entry as a follow-up message
            if state.get("events"):
                await send(ws_name, state["events"][-1])
        except Exception as exc:
            await send("error", f"{label} failed: {exc}")
            await websocket.close()
            return

    # ── Stream structured results after all nodes complete ──────────────────
    result = _build_result(state)

    # Evidence → Stakeholder Intel cell
    for item in result.evidence:
        await send(
            "stakeholder_evidence",
            f"**{item.title}**\n{item.text[:400]}{'…' if len(item.text) > 400 else ''}",
        )

    # Stakeholder findings → Stakeholder Intel cell
    for sr in result.research:
        for finding in sr.findings[:3]:
            await send(
                f"stakeholder_{sr.stakeholder.lower().replace(' ', '_')}",
                f"[{sr.stakeholder}] {finding.claim}",
            )

    # Synthesis → Recommendation cell
    if result.synthesis:
        await send("synthesize_research", result.synthesis.summary)
        for pt in result.synthesis.consensus_points[:5]:
            await send("synthesize_research", f"• {pt}")

    # Recommendation → Recommendation cell
    if result.recommendation:
        rec = result.recommendation
        await send("implement_recommendation", rec.summary)
        if rec.recommended_actions:
            await send(
                "implement_actions",
                "\n".join(f"• {a}" for a in rec.recommended_actions),
            )
        if rec.risks:
            await send(
                "implement_risks",
                "**Risks:**\n" + "\n".join(f"• {r}" for r in rec.risks),
            )
        if rec.implementation_plan and rec.implementation_plan.steps:
            steps_text = "\n\n".join(
                f"**{s.phase}**\n" + "\n".join(f"• {a}" for a in s.actions)
                for s in rec.implementation_plan.steps
            )
            await send("implement_plan", steps_text)

    # Forecast → Forecast cell
    if result.forecast:
        fc = result.forecast
        if fc.mode == "numeric":
            for scenario_attr in ("baseline", "conservative", "expected", "optimistic"):
                sc = getattr(fc, scenario_attr, None)
                if sc:
                    lines = [f"**{sc.name}**"]
                    if sc.gross_revenue:  lines.append(f"Revenue: ${sc.gross_revenue:,.0f}")
                    if sc.net_revenue:    lines.append(f"Net: ${sc.net_revenue:,.0f}")
                    if sc.trip_reduction: lines.append(f"Trip reduction: {sc.trip_reduction:.1%}")
                    if sc.emissions_change: lines.append(f"Emissions Δ: {sc.emissions_change:.1%}")
                    await send("run_forecast", "\n".join(lines))
        else:
            for item in fc.qualitative:
                await send("run_forecast", item)
        if fc.assumptions:
            await send("run_forecast", "**Assumptions:**\n" + "\n".join(f"• {a}" for a in fc.assumptions))

    await send("__end__", "Analysis complete.")
    await websocket.close()
