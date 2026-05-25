/**
 * Editor de templates de email.
 *
 * Lista las 4 plantillas (pedido_creado_cliente, pedido_creado_admin,
 * pedido_confirmado_cliente, recordatorio_retiro) — click en una abre el
 * editor con tabs Editar / Preview / Test.
 *
 * El cuerpo es Jinja2: el usuario puede usar `{{ variable }}` en subject,
 * body_html y body_text. Las variables disponibles se listan en el sidebar
 * del editor (mantener en sincronía con `_pedido_email_context` en
 * `backend/routes/alquileres.py`).
 */

import { createLazyFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, Send, Eye, Pencil, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { adminApi, type EmailTemplate, type EmailTemplateInput } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/email-templates")({
  component: EmailTemplatesPage,
});

// Labels y descripción amigable de cada template. Si se agrega un template
// nuevo en backend, agregar acá también — los que no tengan entry se
// muestran con la `key` cruda.
const TEMPLATE_META: Record<string, { label: string; description: string }> = {
  pedido_creado_cliente: {
    label: "Pedido creado — cliente",
    description: "Confirmación automática al cliente cuando entra un pedido nuevo.",
  },
  pedido_creado_admin: {
    label: "Pedido creado — admin",
    description: "Notificación al equipo cuando entra un pedido nuevo.",
  },
  pedido_confirmado_cliente: {
    label: "Pedido confirmado — cliente",
    description: "Aviso al cliente cuando el admin pasa el pedido a 'confirmado'.",
  },
  recordatorio_retiro: {
    label: "Recordatorio retiro D-1",
    description: "Recordatorio automático al cliente la víspera del retiro.",
  },
};

// Variables que pueden usarse en cualquier template de pedido. Mantener en
// sincronía con `_pedido_email_context()` en backend/routes/alquileres.py.
const AVAILABLE_VARS: { name: string; help: string }[] = [
  { name: "cliente_nombre", help: "Nombre completo del cliente" },
  { name: "cliente_email", help: "Email del cliente" },
  { name: "cliente_telefono", help: "Teléfono del cliente" },
  { name: "numero_pedido", help: "Número público del pedido" },
  { name: "fecha_desde", help: "Fecha de retiro" },
  { name: "fecha_hasta", help: "Fecha de devolución" },
  { name: "total", help: "Monto total del pedido" },
  { name: "notas", help: "Notas que dejó el cliente" },
  { name: "items_html", help: "Lista de equipos como <ul><li>...</li></ul>" },
  { name: "items_text", help: "Lista de equipos como texto plano" },
  { name: "admin_url", help: "Link al pedido en el back-office (solo admin)" },
];

function EmailTemplatesPage() {
  useDocumentTitle("Emails · Back Office");
  const [editingKey, setEditingKey] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["admin", "email-templates"],
    queryFn: () => adminApi.listEmailTemplates(),
    staleTime: 30_000,
  });

  const items = listQ.data?.items ?? [];

  return (
    <div className="px-6 py-6 max-w-5xl mx-auto">
      <header className="mb-6">
        <h1 className="font-display text-3xl text-ink flex items-center gap-2">
          <Mail className="h-6 w-6 text-amber" />
          Emails
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Plantillas de los mails automáticos que envía el sistema (pedidos, confirmaciones,
          recordatorios). Editás el subject + cuerpo HTML + texto plano. Variables Jinja:{" "}
          <code className="font-mono text-xs">{`{{ variable }}`}</code>.
        </p>
      </header>

      {listQ.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}

      {!listQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline bg-muted/20 p-8 text-center">
          <div className="text-sm text-muted-foreground">
            No hay templates. Si recién corriste la migración, refrescá.
          </div>
        </div>
      )}

      <div className="divide-y hairline border hairline rounded-md overflow-hidden">
        {items.map((t) => {
          const meta = TEMPLATE_META[t.key];
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setEditingKey(t.key)}
              className="w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-muted/20 transition"
            >
              <Mail className="h-4 w-4 text-amber shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="font-display text-base text-ink">{meta?.label ?? t.key}</div>
                <div className="text-xs text-muted-foreground mt-0.5 truncate">{t.subject}</div>
                {meta && (
                  <div className="text-[11px] text-muted-foreground/70 mt-0.5">
                    {meta.description}
                  </div>
                )}
              </div>
              <div className="font-mono text-[10px] text-muted-foreground shrink-0 text-right">
                {t.updated_by && <div>por {t.updated_by}</div>}
                {t.updated_at && (
                  <div className="opacity-60">
                    {new Date(t.updated_at).toLocaleDateString("es-AR", {
                      day: "2-digit",
                      month: "short",
                      year: "2-digit",
                    })}
                  </div>
                )}
              </div>
              <Pencil className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-1" />
            </button>
          );
        })}
      </div>

      {editingKey && (
        <TemplateEditorModal
          key={editingKey}
          tplKey={editingKey}
          onClose={() => setEditingKey(null)}
        />
      )}
    </div>
  );
}

function TemplateEditorModal({ tplKey, onClose }: { tplKey: string; onClose: () => void }) {
  const qc = useQueryClient();
  const meta = TEMPLATE_META[tplKey];
  const [tab, setTab] = useState<"edit" | "preview" | "test">("edit");

  const tplQ = useQuery({
    queryKey: ["admin", "email-templates", tplKey],
    queryFn: () => adminApi.getEmailTemplate(tplKey),
  });

  const [form, setForm] = useState<EmailTemplateInput | null>(null);

  // Inicializa form cuando llega el data. Re-init si cambia el key.
  useMemo(() => {
    if (tplQ.data && form === null) {
      setForm({
        subject: tplQ.data.subject,
        body_html: tplQ.data.body_html,
        body_text: tplQ.data.body_text,
      });
    }
  }, [tplQ.data, form]);

  const saveMut = useMutation({
    mutationFn: (input: EmailTemplateInput) => adminApi.updateEmailTemplate(tplKey, input),
    onSuccess: (data: EmailTemplate) => {
      toast.success("Template guardado");
      qc.setQueryData(["admin", "email-templates", tplKey], data);
      qc.invalidateQueries({ queryKey: ["admin", "email-templates"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl max-h-[92vh] rounded-lg bg-background border hairline shadow-lg flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b hairline px-4 py-3 shrink-0">
          <div className="font-display text-base text-ink">{meta?.label ?? tplKey}</div>
          <div className="font-mono text-[10px] text-muted-foreground mt-0.5">key: {tplKey}</div>
        </header>

        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as typeof tab)}
          className="flex-1 flex flex-col min-h-0"
        >
          <TabsList className="mx-4 mt-3 shrink-0 w-fit">
            <TabsTrigger value="edit">
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Editar
            </TabsTrigger>
            <TabsTrigger value="preview">
              <Eye className="h-3.5 w-3.5 mr-1.5" />
              Preview
            </TabsTrigger>
            <TabsTrigger value="test">
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Test
            </TabsTrigger>
          </TabsList>

          {tplQ.isLoading && <div className="p-6 text-sm text-muted-foreground">Cargando…</div>}

          {form && tplQ.data && (
            <>
              <TabsContent value="edit" className="flex-1 overflow-y-auto p-4 m-0">
                <EditTab form={form} setForm={setForm} />
              </TabsContent>
              <TabsContent value="preview" className="flex-1 overflow-y-auto p-4 m-0">
                <PreviewTab tplKey={tplKey} />
              </TabsContent>
              <TabsContent value="test" className="flex-1 overflow-y-auto p-4 m-0">
                <TestTab tplKey={tplKey} />
              </TabsContent>
            </>
          )}
        </Tabs>

        <footer className="border-t hairline px-4 py-3 flex justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={onClose} disabled={saveMut.isPending}>
            Cerrar
          </Button>
          {tab === "edit" && form && (
            <Button onClick={() => saveMut.mutate(form)} disabled={saveMut.isPending}>
              {saveMut.isPending ? "Guardando…" : "Guardar"}
            </Button>
          )}
        </footer>
      </div>
    </div>
  );
}

function EditTab({
  form,
  setForm,
}: {
  form: EmailTemplateInput;
  setForm: (f: EmailTemplateInput) => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_220px] gap-4">
      <div className="space-y-3 min-w-0">
        <div>
          <Label className="text-xs">Subject</Label>
          <Input
            value={form.subject}
            onChange={(e) => setForm({ ...form, subject: e.target.value })}
            placeholder="ej. Tu pedido #{{ numero_pedido }}"
          />
        </div>
        <div>
          <Label className="text-xs">Body HTML</Label>
          <textarea
            value={form.body_html}
            onChange={(e) => setForm({ ...form, body_html: e.target.value })}
            rows={12}
            className="w-full rounded-md border hairline bg-surface px-3 py-2 text-xs font-mono leading-relaxed focus:border-amber focus:ring-[3px] focus:ring-amber/20 focus:outline-none"
            placeholder="<p>Hola {{ cliente_nombre }}…</p>"
          />
        </div>
        <div>
          <Label className="text-xs">Body texto plano</Label>
          <textarea
            value={form.body_text}
            onChange={(e) => setForm({ ...form, body_text: e.target.value })}
            rows={8}
            className="w-full rounded-md border hairline bg-surface px-3 py-2 text-xs font-mono leading-relaxed focus:border-amber focus:ring-[3px] focus:ring-amber/20 focus:outline-none"
            placeholder="Hola {{ cliente_nombre }}…"
          />
        </div>
      </div>
      <aside className="border-l hairline pl-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
          Variables
        </div>
        <ul className="space-y-1.5 text-[11px]">
          {AVAILABLE_VARS.map((v) => (
            <li key={v.name}>
              <code className="font-mono text-ink">{`{{ ${v.name} }}`}</code>
              <div className="text-[10px] text-muted-foreground/70">{v.help}</div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function PreviewTab({ tplKey }: { tplKey: string }) {
  const previewQ = useQuery({
    queryKey: ["admin", "email-templates", tplKey, "preview"],
    queryFn: () => adminApi.previewEmailTemplate(tplKey),
  });

  if (previewQ.isLoading) {
    return <div className="text-sm text-muted-foreground">Renderizando…</div>;
  }
  if (previewQ.isError) {
    return (
      <div className="text-sm text-destructive">Error: {(previewQ.error as Error).message}</div>
    );
  }
  const d = previewQ.data!;
  return (
    <div className="space-y-4">
      <p className="text-[11px] text-muted-foreground">
        Renderizado con datos de ejemplo. Después de guardar cambios refrescá esta pestaña.
      </p>
      <div>
        <Label className="text-xs">Subject</Label>
        <div className="border hairline rounded-md bg-muted/20 px-3 py-2 text-sm">{d.subject}</div>
      </div>
      <div>
        <Label className="text-xs">HTML</Label>
        {/* email-frame: el mail centrado sobre fondo muted (ancho típico de
            email ~600px), como el mock del handoff. */}
        <div className="flex justify-center rounded-md border hairline bg-muted/30 p-4">
          <iframe
            srcDoc={d.html}
            sandbox=""
            className="w-full max-w-[600px] h-96 rounded-md bg-white shadow-sm border hairline"
            title="preview html"
          />
        </div>
      </div>
      <div>
        <Label className="text-xs">Texto plano</Label>
        <pre className="border hairline rounded-md bg-muted/20 px-3 py-2 text-xs whitespace-pre-wrap font-mono">
          {d.text}
        </pre>
      </div>
    </div>
  );
}

function TestTab({ tplKey }: { tplKey: string }) {
  const [to, setTo] = useState("");
  const sendMut = useMutation({
    mutationFn: () => adminApi.testEmailTemplate(tplKey, to),
    onSuccess: (data) => {
      if (data.ok) {
        toast.success(
          `Enviado (provider ${data.provider}${data.provider_id ? ` · id ${data.provider_id}` : ""})`,
        );
      } else {
        toast.error(data.error ?? "Falló el envío");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-[11px] text-muted-foreground">
        Envía un mail real al destinatario que pongas. Se loggea en
        <code className="font-mono ml-1">emails_log</code> con el resto. Usa los cambios{" "}
        <strong>guardados</strong> del template (no los del editor).
      </p>
      <div>
        <Label className="text-xs">Enviar a</Label>
        <Input
          type="email"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="tu@email.com"
        />
      </div>
      <Button
        onClick={() => sendMut.mutate()}
        disabled={!to || !to.includes("@") || sendMut.isPending}
      >
        {sendMut.isPending ? (
          <>
            <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            Enviando…
          </>
        ) : (
          <>
            <Send className="h-3.5 w-3.5 mr-1.5" />
            Enviar test
          </>
        )}
      </Button>
    </div>
  );
}
