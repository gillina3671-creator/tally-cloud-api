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

SUPABASE_URL = https://nigqhmuzwxxtneenibet.supabase.co
SUPABASE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5pZ3FobXV6d3h4dG5lZW5pYmV0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5NzQ4MjMsImV4cCI6MjA4NjU1MDgyM30.grVUgGJq3WVnaMmDiPZ0LOGIFdfVhZZzTVP90TV7Qcs
API_SECRET = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5pZ3FobXV6d3h4dG5lZW5pYmV0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDk3NDgyMywiZXhwIjoyMDg2NTUwODIzfQ.uTROpfcrO5pJJypWSLoVGtBKSzQVlIKc37RrbQY49iE
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def verify_agent_token(x_agent_token: str = Header(...)):
    if x_agent_token != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return x_agent_token

def get_or_create_company(company_name: str) -> str:
    result = supabase.table('companies').select('id').eq('name', company_name).execute()
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
# SYNC ENDPOINTS
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
                name = ledger.get('name', '').strip()
                if not name:
                    continue

                ledger['company_id'] = company_id
                ledger['updated_at'] = datetime.now().isoformat()

                # Check if record exists
                existing = supabase.table('ledgers')\
                    .select('id')\
                    .eq('company_id', company_id)\
                    .eq('name', name)\
                    .execute()

                if existing.data:
                    # UPDATE existing record
                    supabase.table('ledgers')\
                        .update(ledger)\
                        .eq('company_id', company_id)\
                        .eq('name', name)\
                        .execute()
                else:
                    # INSERT new record
                    ledger['created_at'] = datetime.now().isoformat()
                    supabase.table('ledgers').insert(ledger).execute()

                synced += 1

            except Exception as e:
                errors.append(f"{ledger.get('name', 'Unknown')}: {str(e)}")

        # Log sync history
        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'ledgers',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors[:10]) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {
            "success": True,
            "company": company_name,
            "total": len(ledgers),
            "synced": synced,
            "failed": len(errors),
            "errors": errors[:5] if errors else None
        }
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
                name = item.get('name', '').strip()
                if not name:
                    continue

                item['company_id'] = company_id
                item['updated_at'] = datetime.now().isoformat()

                # Check if record exists
                existing = supabase.table('stock_items')\
                    .select('id')\
                    .eq('company_id', company_id)\
                    .eq('name', name)\
                    .execute()

                if existing.data:
                    # UPDATE existing record
                    supabase.table('stock_items')\
                        .update(item)\
                        .eq('company_id', company_id)\
                        .eq('name', name)\
                        .execute()
                else:
                    # INSERT new record
                    item['created_at'] = datetime.now().isoformat()
                    supabase.table('stock_items').insert(item).execute()

                synced += 1

            except Exception as e:
                errors.append(f"{item.get('name', 'Unknown')}: {str(e)}")

        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'stock_items',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors[:10]) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {
            "success": True,
            "company": company_name,
            "total": len(stock_items),
            "synced": synced,
            "failed": len(errors)
        }
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
                bill_name = bill.get('bill_name', '').strip()
                bill_type = bill.get('type', '').strip()
                if not bill_name or not bill_type:
                    continue

                bill['company_id'] = company_id
                bill['updated_at'] = datetime.now().isoformat()

                # Check if record exists
                existing = supabase.table('outstanding')\
                    .select('id')\
                    .eq('company_id', company_id)\
                    .eq('bill_name', bill_name)\
                    .eq('type', bill_type)\
                    .execute()

                if existing.data:
                    # UPDATE existing record
                    supabase.table('outstanding')\
                        .update(bill)\
                        .eq('company_id', company_id)\
                        .eq('bill_name', bill_name)\
                        .eq('type', bill_type)\
                        .execute()
                else:
                    # INSERT new record
                    bill['created_at'] = datetime.now().isoformat()
                    supabase.table('outstanding').insert(bill).execute()

                synced += 1

            except Exception as e:
                errors.append(f"{bill.get('bill_name', 'Unknown')}: {str(e)}")

        supabase.table('sync_history').insert({
            'company_id': company_id,
            'sync_type': 'outstanding',
            'records_synced': synced,
            'status': 'success' if not errors else 'partial',
            'error_message': '\n'.join(errors[:10]) if errors else None,
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat()
        }).execute()

        return {
            "success": True,
            "company": company_name,
            "total": len(outstanding),
            "synced": synced,
            "failed": len(errors)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# READ ENDPOINTS
# ============================================================

@app.get("/api/ledgers")
def get_ledgers(
    company_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
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
def get_stock_items(
    company_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
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
        stock = supabase.table('stock_items').select('id', count='exact').eq('company_id', company_id).execute()
        recv = supabase.table('outstanding').select('id', count='exact').eq('company_id', company_id).eq('type', 'receivable').execute()
        pay = supabase.table('outstanding').select('id', count='exact').eq('company_id', company_id).eq('type', 'payable').execute()
        last_sync = supabase.table('sync_history').select('*').eq('company_id', company_id).order('started_at', desc=True).limit(1).execute()

        return {
            "success": True,
            "company_name": company_name,
            "total_ledgers": ledgers.count or len(ledgers.data),
            "total_stock_items": stock.count or len(stock.data),
            "total_receivables": recv.count or len(recv.data),
            "total_payables": pay.count or len(pay.data),
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
