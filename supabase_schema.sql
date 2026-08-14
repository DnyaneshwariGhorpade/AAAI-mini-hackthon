-- Run this in Supabase Dashboard > SQL Editor
-- Schema for MediRAG chat: sessions + messages with RLS per user

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New chat',
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  sources jsonb,
  created_at timestamptz not null default now()
);

create index if not exists chat_sessions_user_idx on public.chat_sessions (user_id);
create index if not exists chat_messages_session_idx on public.chat_messages (session_id, created_at);

alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "users select own sessions" on public.chat_sessions;
drop policy if exists "users insert own sessions" on public.chat_sessions;
drop policy if exists "users update own sessions" on public.chat_sessions;
drop policy if exists "users delete own sessions" on public.chat_sessions;

create policy "users select own sessions"
  on public.chat_sessions for select
  using (auth.uid() = user_id);

create policy "users insert own sessions"
  on public.chat_sessions for insert
  with check (auth.uid() = user_id);

create policy "users update own sessions"
  on public.chat_sessions for update
  using (auth.uid() = user_id);

create policy "users delete own sessions"
  on public.chat_sessions for delete
  using (auth.uid() = user_id);

drop policy if exists "users select own messages" on public.chat_messages;
drop policy if exists "users insert own messages" on public.chat_messages;
drop policy if exists "users delete own messages" on public.chat_messages;

create policy "users select own messages"
  on public.chat_messages for select
  using (exists (
    select 1 from public.chat_sessions s
    where s.id = session_id and s.user_id = auth.uid()
  ));

create policy "users insert own messages"
  on public.chat_messages for insert
  with check (exists (
    select 1 from public.chat_sessions s
    where s.id = session_id and s.user_id = auth.uid()
  ));

create policy "users delete own messages"
  on public.chat_messages for delete
  using (exists (
    select 1 from public.chat_sessions s
    where s.id = session_id and s.user_id = auth.uid()
  ));
