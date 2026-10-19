create extension if not exists pgcrypto;
create table if not exists public.loan_cases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  case_name text not null,
  borrower text,
  loan_reference text,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.loan_cases enable row level security;
drop policy if exists "Users view own cases" on public.loan_cases;
create policy "Users view own cases" on public.loan_cases for select using (auth.uid()=user_id);
drop policy if exists "Users insert own cases" on public.loan_cases;
create policy "Users insert own cases" on public.loan_cases for insert with check (auth.uid()=user_id);
drop policy if exists "Users update own cases" on public.loan_cases;
create policy "Users update own cases" on public.loan_cases for update using (auth.uid()=user_id) with check (auth.uid()=user_id);
drop policy if exists "Users delete own cases" on public.loan_cases;
create policy "Users delete own cases" on public.loan_cases for delete using (auth.uid()=user_id);
