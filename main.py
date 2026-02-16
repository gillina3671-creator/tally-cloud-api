from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List, Dict
import os

app = FastAPI(title="Tally Cloud Sync API")

# CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration - Replace these with your actual values
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://niigqhmuzwxxtneenibet.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5pZ3FobXV6d3h4dG5lZW5pYmV0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5NzQ4MjMsImV4cCI6MjA4NjU1MDgyM30.grVUgGJq3WVnaMmDiPZ0LOGIFdfVhZZzTVP90TV7Qcs")
API_SECRET = os.getenv("API_SECRET", "my-secret-token-12345")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Authentication
def verify_agent_token(x_agent_token: str = Header(...)):
    """Verify desktop agent token"""
    if x_agent_token != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return x_agent_token

@app.get("/")
def home():
    return {
        "app": "Tally Cloud Sync API",
        "version": "1.0",
        "status": "running",
        "endpoints": {
            "POST /api/sync/ledgers": "Receive ledgers from desktop agent",
            "GET /api/ledgers": "Get ledgers from database",
            "GET /api/companies": "Get all companies",
            "GET /api/sync/status/{company}": "Get sync status"
        }
    }

@app.post("/api/sync/ledgers")
async def receive_ledgers_from_agent(
    ledgers: List[Dict],
    company_name: str,
    token: str = Depends(verify_agent_token)
):
    """Receive and store ledgers from desktop agent"""
    try:
        # Get or create company
        company_result = supabase.table('companies').select('*').eq('name', company_name).execute()
        
        if len(company_result.data) == 0:
            company = supabase.table('companies').insert({'name': company_name}).execute()
            company_id = company.data[0]['id']
        else:
            company_id = company_result.data[0]['id']
        
        # Store ledgers
        synced = 0
        errors = []
        
        for ledger in ledgers:
            try:
                ledger['company_id'] = company_id
                ledger['updated_at'] = datetime.now().isoformat()
                
                supabase.table('ledgers').upsert(
                    ledger,
                    on_conflict='company_id,name'
                ).execute()
                synced += 1
            except Exception as e:
                errors.append(f"{ledger.get('name', 'Unknown')}: {str(e)}")
        
        # Log sync
        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'ledgers',
            'records_synced': synced,
            'status': 'success' if len(errors) == 0 else 'partial',
            'error_message': '\n'.join(errors) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()
        
        return {
            "success": True,
            "company_id": company_id,
            "total": len(ledgers),
            "synced": synced,
            "failed": len(errors),
            "errors": errors if errors else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ledgers")
def get_ledgers(
    company_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get ledgers from database"""
    try:
        query = supabase.table('ledgers').select('*')
        
        if company_name:
            company = supabase.table('companies').select('id').eq('name', company_name).execute()
            if company.data:
                query = query.eq('company_id', company.data[0]['id'])
        
        result = query.order('name').range(offset, offset + limit - 1).execute()
        
        return {
            "success": True,
            "total": len(result.data),
            "ledgers": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ledgers/search/{query}")
def search_ledgers(query: str, company_name: Optional[str] = None):
    """Search ledgers by name"""
    try:
        db_query = supabase.table('ledgers').select('*').ilike('name', f'%{query}%')
        
        if company_name:
            company = supabase.table('companies').select('id').eq('name', company_name).execute()
            if company.data:
                db_query = db_query.eq('company_id', company.data[0]['id'])
        
        result = db_query.limit(50).execute()
        
        return {
            "success": True,
            "query": query,
            "results": len(result.data),
            "ledgers": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies")
def get_companies():
    """Get all companies"""
    try:
        result = supabase.table('companies').select('*').order('name').execute()
        return {
            "success": True,
            "total": len(result.data),
            "companies": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sync/status/{company_name}")
def get_sync_status(company_name: str):
    """Get latest sync status"""
    try:
        company = supabase.table('companies').select('id').eq('name', company_name).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        company_id = company.data[0]['id']
        
        history = supabase.table('sync_history')\
            .select('*')\
            .eq('company_id', company_id)\
            .order('started_at', desc=True)\
            .limit(5)\
            .execute()
        
        return {
            "success": True,
            "company_name": company_name,
            "sync_history": history.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/{company_name}")
def get_stats(company_name: str):
    """Get statistics for a company"""
    try:
        company = supabase.table('companies').select('id').eq('name', company_name).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        company_id = company.data[0]['id']
        
        # Count ledgers
        ledgers = supabase.table('ledgers').select('id', count='exact').eq('company_id', company_id).execute()
        
        # Get last sync
        last_sync = supabase.table('sync_history')\
            .select('*')\
            .eq('company_id', company_id)\
            .order('started_at', desc=True)\
            .limit(1)\
            .execute()
        
        return {
            "success": True,
            "company_name": company_name,
            "total_ledgers": ledgers.count if hasattr(ledgers, 'count') else len(ledgers.data),
            "last_sync": last_sync.data[0] if last_sync.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))