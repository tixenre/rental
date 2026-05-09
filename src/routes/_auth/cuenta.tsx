import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, LogOut } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";
import { isAdminEmail, BACKOFFICE_URL } from "@/lib/admin-emails";

export const Route = createFileRoute("/_auth/cuenta")({
  head: () => ({ meta: [{ title: "Mi cuenta — Rambla Rental" }] }),
  component: AccountPage,
});

type ProfileForm = {
  full_name: string;
  phone: string;
  company: string;
  address: string;
  dni: string;
  cuit: string;
  tax_condition: string;
};

const empty: ProfileForm = {
  full_name: "",
  phone: "",
  company: "",
  address: "",
  dni: "",
  cuit: "",
  tax_condition: "",
};

function AccountPage() {
  const { user, signOut } = useAuth();
  const qc = useQueryClient();
  const [form, setForm] = useState<ProfileForm>(empty);
  const [saved, setSaved] = useState(false);

  const { data } = useQuery({
    queryKey: ["profile", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase.from("profiles").select("*").eq("id", user!.id).single();
      if (error) throw error;
      return data;
    },
  });

  useEffect(() => {
    if (data) {
      setForm({
        full_name: data.full_name ?? "",
        phone: data.phone ?? "",
        company: data.company ?? "",
        address: data.address ?? "",
        dni: data.dni ?? "",
        cuit: data.cuit ?? "",
        tax_condition: data.tax_condition ?? "",
      });
    }
  }, [data]);

  const saveMut = useMutation({
    mutationFn: async () => {
      const { error } = await supabase
        .from("profiles")
        .update({ ...form })
        .eq("id", user!.id);
      if (error) throw error;
    },
    onSuccess: () => {
      setSaved(true);
      qc.invalidateQueries({ queryKey: ["profile"] });
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const field = (k: keyof ProfileForm, label: string, placeholder?: string) => (
    <label className="block">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <input
        value={form[k]}
        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber"
      />
    </label>
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b hairline px-4 py-4 md:px-8 flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Catálogo
        </Link>
        <button
          onClick={() => signOut()}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive"
        >
          <LogOut className="h-3.5 w-3.5" /> Cerrar sesión
        </button>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-8 md:px-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Tu cuenta
        </div>
        <h1 className="font-display text-3xl text-ink">Datos para presupuestos</h1>
        <p className="mt-2 text-sm text-muted-foreground">{user?.email}</p>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {field("full_name", "Nombre completo")}
          {field("phone", "Teléfono", "+54 9 ...")}
          {field("company", "Productora / Empresa")}
          {field("address", "Dirección")}
          {field("dni", "DNI")}
          {field("cuit", "CUIT")}
          <div className="md:col-span-2">{field("tax_condition", "Condición fiscal", "Responsable Inscripto / Monotributo / Consumidor Final")}</div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3">
          {saved && <span className="text-xs text-green-700">Guardado ✓</span>}
          <button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
            className="rounded-md bg-amber px-4 py-2 text-sm font-medium uppercase tracking-widest text-ink hover:brightness-110 disabled:opacity-50"
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
