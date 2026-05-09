-- Enum de estados de pedido
create type public.order_status as enum ('borrador','solicitado','confirmado','entregado','devuelto','cancelado');
create type public.change_request_status as enum ('pendiente','aceptado','rechazado');

-- Profiles
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  phone text,
  company text,
  address text,
  dni text,
  cuit text,
  tax_condition text,
  email text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;

create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id);

-- Auto profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- updated_at helper
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- Orders
create table public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  status public.order_status not null default 'borrador',
  start_date date,
  end_date date,
  start_time text,
  end_time text,
  days integer not null default 1,
  subtotal_per_day numeric(12,2) not null default 0,
  total numeric(12,2) not null default 0,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.orders enable row level security;

create policy "orders_select_own" on public.orders for select using (auth.uid() = user_id);
create policy "orders_insert_own" on public.orders for insert with check (auth.uid() = user_id);
create policy "orders_update_own" on public.orders for update using (
  auth.uid() = user_id and status in ('borrador','solicitado')
);
create policy "orders_delete_own" on public.orders for delete using (
  auth.uid() = user_id and status in ('borrador','solicitado')
);

create trigger orders_set_updated_at
  before update on public.orders
  for each row execute function public.set_updated_at();

create index orders_user_idx on public.orders(user_id, created_at desc);

-- Order items
create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  equipment_id text not null,
  name text not null,
  brand text,
  category text,
  qty integer not null check (qty > 0),
  price_per_day numeric(12,2) not null default 0,
  created_at timestamptz not null default now()
);
alter table public.order_items enable row level security;

create policy "order_items_select_own" on public.order_items for select using (
  exists (select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid())
);
create policy "order_items_insert_own" on public.order_items for insert with check (
  exists (select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid()
    and o.status in ('borrador','solicitado'))
);
create policy "order_items_update_own" on public.order_items for update using (
  exists (select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid()
    and o.status in ('borrador','solicitado'))
);
create policy "order_items_delete_own" on public.order_items for delete using (
  exists (select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid()
    and o.status in ('borrador','solicitado'))
);

create index order_items_order_idx on public.order_items(order_id);

-- Change requests
create table public.order_change_requests (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  status public.change_request_status not null default 'pendiente',
  message text not null,
  proposed_changes jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.order_change_requests enable row level security;

create policy "ocr_select_own" on public.order_change_requests for select using (auth.uid() = user_id);
create policy "ocr_insert_own" on public.order_change_requests for insert with check (
  auth.uid() = user_id and exists (
    select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid()
  )
);
create policy "ocr_update_own_pending" on public.order_change_requests for update using (
  auth.uid() = user_id and status = 'pendiente'
);
create policy "ocr_delete_own_pending" on public.order_change_requests for delete using (
  auth.uid() = user_id and status = 'pendiente'
);

create trigger ocr_set_updated_at
  before update on public.order_change_requests
  for each row execute function public.set_updated_at();

create index ocr_order_idx on public.order_change_requests(order_id, created_at desc);