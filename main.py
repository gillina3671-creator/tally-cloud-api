from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List, Dict
import os

app = FastAPI(title="Tally Cloud Sync API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
API_SECRET = os.getenv("API_SECRET", "my-secret-token-12345")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def verify_agent_token(x_agent_token: str = Header(...)):
    if x_agent_token != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return x_agent_token

def get_or_create_company(company_name: str) -> str:
    result = supabase.table('companies').select('*').eq('name', company_name).execute()
    if len(result.data) == 0:
        company = supabase.table('companies').insert({'name': company_name}).execute()
        return company.data[0]['id']
    return result.data[0]['id']

@app.get("/")
def home():
    return {
        "app": "Tally Cloud Sync API",
        "version": "2.0",
        "status": "running",
        "endpoints": {
            "POST /api/sync/ledgers": "Sync ledgers",
            "POST /api/sync/stock-items": "Sync stock items",
            "POST /api/sync/outstanding": "Sync outstanding",
            "GET /api/ledgers": "Get ledgers",
            "GET /api/stock-items": "Get stock items",
            "GET /api/outstanding": "Get outstanding",
            "GET /api/companies": "Get companies",
            "GET /api/stats/{company}": "Get stats"
        }
    }

# ============================================================
# SYNC ENDPOINTS (called by desktop agent)
# ============================================================

@app.post("/api/sync/ledgers")
async def sync_ledgers(
    ledgers: List[Dict],
    company_name: str,
    token: str = Depends(verify_agent_token)
):
    try:
        company_id = get_or_create_company(company_name)
        synced = 0
        errors = []

        for ledger in ledgers:
            try:
                ledger['company_id'] = company_id
                ledger['updated_at'] = datetime.now().isoformat()
                supabase.table('ledgers').upsert(ledger, on_conflict='company_id,name').execute()
                synced += 1
            except Exception as e:
                errors.append(f"{ledger.get('name', 'Unknown')}: {str(e)}")

        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'ledgers',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {"success": True, "company": company_name, "total": len(ledgers), "synced": synced, "failed": len(errors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/stock-items")
async def sync_stock_items(
    stock_items: List[Dict],
    company_name: str,
    token: str = Depends(verify_agent_token)
):
    try:
        company_id = get_or_create_company(company_name)
        synced = 0
        errors = []

        for item in stock_items:
            try:
                item['company_id'] = company_id
                item['updated_at'] = datetime.now().isoformat()
                supabase.table('stock_items').upsert(item, on_conflict='company_id,name').execute()
                synced += 1
            except Exception as e:
                errors.append(f"{item.get('name', 'Unknown')}: {str(e)}")

        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'stock_items',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {"success": True, "company": company_name, "total": len(stock_items), "synced": synced, "failed": len(errors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/outstanding")
async def sync_outstanding(
    outstanding: List[Dict],
    company_name: str,
    token: str = Depends(verify_agent_token)
):
    try:
        company_id = get_or_create_company(company_name)
        synced = 0
        errors = []

        for bill in outstanding:
            try:
                bill['company_id'] = company_id
                bill['updated_at'] = datetime.now().isoformat()
                supabase.table('outstanding').upsert(bill, on_conflict='company_id,bill_name,type').execute()
                synced += 1
            except Exception as e:
                errors.append(f"{bill.get('bill_name', 'Unknown')}: {str(e)}")

        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'outstanding',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {"success": True, "company": company_name, "total": len(outstanding), "synced": synced, "failed": len(errors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# READ ENDPOINTS (for dashboard/apps)
# ============================================================

@app.get("/api/ledgers")
def get_ledgers(company_name: Optional[str] = None, limit: int = 100, offset: int = 0):
    try:
        query = supabase.table('ledgers').select('*')
        if company_name:
            company = supabase.table('companies').select('id').eq('name', company_name).execute()
            if company.data:
                query = query.eq('company_id', company.data[0]['id'])
        result = query.order('name').range(offset, offset + limit - 1).execute()
        return {"success": True, "total": len(result.data), "ledgers": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock-items")
def get_stock_items(company_name: Optional[str] = None, limit: int = 100, offset: int = 0):
    try:
        query = supabase.table('stock_items').select('*')
        if company_name:
            company = supabase.table('companies').select('id').eq('name', company_name).execute()
            if company.data:
                query = query.eq('company_id', company.data[0]['id'])
        result = query.order('name').range(offset, offset + limit - 1).execute()
        return {"success": True, "total": len(result.data), "stock_items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/outstanding")
def get_outstanding(
    company_name: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    try:
        query = supabase.table('outstanding').select('*')
        if company_name:
            company = supabase.table('companies').select('id').eq('name', company_name).execute()
            if company.data:
                query = query.eq('company_id', company.data[0]['id'])
        if type:
            query = query.eq('type', type)
        result = query.order('bill_name').range(offset, offset + limit - 1).execute()
        return {"success": True, "total": len(result.data), "outstanding": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/companies")
def get_companies():
    try:
        result = supabase.table('companies').select('*').order('name').execute()
        return {"success": True, "total": len(result.data), "companies": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/{company_name}")
def get_stats(company_name: str):
    try:
        company = supabase.table('companies').select('id').eq('name', company_name).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = company.data[0]['id']

        ledgers = supabase.table('ledgers').select('id', count='exact').eq('company_id', company_id).execute()
        stock_items = supabase.table('stock_items').select('id', count='exact').eq('company_id', company_id).execute()
        receivables = supabase.table('outstanding').select('id', count='exact').eq('company_id', company_id).eq('type', 'receivable').execute()
        payables = supabase.table('outstanding').select('id', count='exact').eq('company_id', company_id).eq('type', 'payable').execute()

        last_sync = supabase.table('sync_history').select('*').eq('company_id', company_id).order('started_at', desc=True).limit(1).execute()

        return {
            "success": True,
            "company_name": company_name,
            "total_ledgers": ledgers.count or len(ledgers.data),
            "total_stock_items": stock_items.count or len(stock_items.data),
            "total_receivables": receivables.count or len(receivables.data),
            "total_payables": payables.count or len(payables.data),
            "last_sync": last_sync.data[0] if last_sync.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/status/{company_name}")
def get_sync_status(company_name: str):
    try:
        company = supabase.table('companies').select('id').eq('name', company_name).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")
        company_id = company.data[0]['id']
        history = supabase.table('sync_history').select('*').eq('company_id', company_id).order('started_at', desc=True).limit(10).execute()
        return {"success": True, "company_name": company_name, "sync_history": history.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))