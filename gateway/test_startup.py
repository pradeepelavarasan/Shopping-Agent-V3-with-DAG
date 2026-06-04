import sys
print("Starting import test...")

import os, time, json
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
print("Core imports done")

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import Draft202012Validator, ValidationError
print("FastAPI / JSONSchema imports done")

import db
print("db import done")

import providers as P
print("providers import done")

from router import Router, RouterPool, DEFAULT_ROUTER_ORDER, LIMITS, SHORTCUTS, resolve
print("router import done")

from cache import GeminiCache
print("cache import done")

from schemas import ChatRequest, ChatResponse, ToolCall, RouterDecision, EmbedRequest, EmbedResponse, BatchChatRequest
print("schemas import done")

import embedders as E
print("embedders import done")

print("All imports completed successfully!")
