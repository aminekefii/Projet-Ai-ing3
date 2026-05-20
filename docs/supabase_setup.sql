-- Supabase schema for ProjetAI research-paper agent.
-- Paste this into the Supabase Dashboard → SQL Editor → New Query → Run.
-- Then create a private Storage bucket named 'paper-files' from the dashboard.

-- ---------- papers ----------
create table if not exists public.papers (
    id            uuid primary key,
    topic         text not null,
    mode          text not null check (mode in ('survey', 'empirical', 'term')),
    status        text not null default 'in_progress'
                  check (status in ('in_progress', 'complete')),
    final_output  text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists papers_status_updated_idx
    on public.papers (status, updated_at desc);

-- ---------- paper_files ----------
create table if not exists public.paper_files (
    id            uuid primary key default gen_random_uuid(),
    paper_id      uuid not null references public.papers(id) on delete cascade,
    file_name     text not null,
    file_size     int  not null,
    storage_path  text not null,
    uploaded_at   timestamptz not null default now()
);

create index if not exists paper_files_paper_idx on public.paper_files (paper_id);
