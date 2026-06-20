import { useRef, useState } from "react";
import { Upload, CheckCircle2, AlertCircle, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiUploadComprobante, apiCrearInscripcion, type Taller } from "@/lib/api";
import { formatARS } from "@/lib/format";

type Props = {
  taller: Taller;
  onSuccess?: (enListaEspera: boolean) => void;
};

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "done"; url: string; fileName: string }
  | { status: "error"; message: string };

type SubmitState = "idle" | "submitting" | "success_normal" | "success_espera" | "error";

export function WorkshopInscripcionForm({ taller, onSuccess }: Props) {
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");
  const [experiencia, setExperiencia] = useState("");
  const [upload, setUpload] = useState<UploadState>({ status: "idle" });
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const fileRef = useRef<HTMLInputElement>(null);

  const cuposDisponibles = Math.max(0, taller.cupos_total - taller.cupos_confirmados);
  const enListaActual = cuposDisponibles === 0;

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const maxMB = 10;
    if (file.size > maxMB * 1024 * 1024) {
      toast.error(`El archivo no puede superar ${maxMB} MB`);
      return;
    }
    setUpload({ status: "uploading" });
    try {
      const url = await apiUploadComprobante(taller.slug, file);
      setUpload({ status: "done", url, fileName: file.name });
    } catch (err) {
      setUpload({
        status: "error",
        message: err instanceof Error ? err.message : "No se pudo subir el archivo",
      });
    }
  };

  const removeFile = () => {
    setUpload({ status: "idle" });
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nombre.trim() || !email.trim() || !telefono.trim()) {
      toast.error("Completá nombre, email y teléfono");
      return;
    }
    setSubmitState("submitting");
    try {
      const result = await apiCrearInscripcion(taller.slug, {
        nombre: nombre.trim(),
        email: email.trim(),
        telefono: telefono.trim(),
        experiencia: experiencia.trim() || undefined,
        comprobante_url: upload.status === "done" ? upload.url : undefined,
      });
      setSubmitState(result.en_lista_espera ? "success_espera" : "success_normal");
      onSuccess?.(result.en_lista_espera);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Algo salió mal. Intentá de nuevo.");
      setSubmitState("error");
    }
  };

  if (submitState === "success_normal" || submitState === "success_espera") {
    const isEspera = submitState === "success_espera";
    return (
      <div className="rounded-2xl border border-border/60 bg-background p-6 sm:p-8 text-center">
        <CheckCircle2
          className={`mx-auto mb-4 h-10 w-10 ${isEspera ? "text-amber" : "text-green-500"}`}
          strokeWidth={1.5}
        />
        <h3 className="font-display text-xl font-bold text-ink mb-2">
          {isEspera ? "Quedaste en lista de espera" : "¡Tu lugar está reservado!"}
        </h3>
        <p className="text-sm text-muted-foreground max-w-xs mx-auto">
          {isEspera
            ? "Los cupos están completos, pero te anotamos en la lista de espera. Te avisamos si se libera un lugar."
            : "Recibimos tu inscripción. Te enviamos un mail de confirmación con los datos de pago."}
        </p>
        {!isEspera && (
          <div className="mt-6 rounded-xl bg-muted/40 p-4 text-left text-sm">
            <p className="font-medium text-ink mb-2">Datos para la seña ({formatARS(taller.precio_sena)})</p>
            <p className="text-muted-foreground leading-relaxed">
              Alias: <span className="text-ink font-mono">{taller.pago_alias}</span>
              <br />
              CBU: <span className="text-ink font-mono text-xs">{taller.pago_cbu}</span>
              <br />
              Banco: {taller.pago_banco}
            </p>
          </div>
        )}
        <p className="mt-5 text-xs text-muted-foreground">
          Seguramente en los próximos días tendrás un nuevo grupo de WhatsApp :)
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* Cupos badge */}
      <div
        className={`rounded-xl px-4 py-2.5 text-sm font-medium ${
          enListaActual
            ? "bg-amber/15 text-amber-700"
            : cuposDisponibles <= 3
              ? "bg-amber/10 text-amber-700"
              : "bg-green-50 text-green-700"
        }`}
      >
        {enListaActual
          ? "Los cupos están completos — podés anotarte en la lista de espera"
          : cuposDisponibles === 1
            ? "¡Queda 1 lugar disponible!"
            : `${cuposDisponibles} lugares disponibles`}
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ins-nombre">Nombre y apellido *</Label>
          <Input
            id="ins-nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Juana García"
            required
            disabled={submitState === "submitting"}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ins-telefono">Teléfono celular *</Label>
          <Input
            id="ins-telefono"
            type="tel"
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
            placeholder="+54 9 223 000-0000"
            required
            disabled={submitState === "submitting"}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ins-email">Mail *</Label>
        <Input
          id="ins-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="vos@ejemplo.com"
          required
          disabled={submitState === "submitting"}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ins-exp">
          ¿Tenés algún tipo de experiencia en arte?{" "}
          <span className="text-muted-foreground font-normal text-xs">
            (no es necesario para inscribirte, es solo curiosidad :)
          </span>
        </Label>
        <Textarea
          id="ins-exp"
          value={experiencia}
          onChange={(e) => setExperiencia(e.target.value)}
          placeholder="Contanos brevemente, si querés…"
          rows={3}
          disabled={submitState === "submitting"}
        />
      </div>

      {/* Comprobante upload */}
      <div className="flex flex-col gap-1.5">
        <Label>Comprobante de transferencia</Label>
        <p className="text-xs text-muted-foreground -mt-0.5">
          Para reservar tu cupo, realizá el pago del 50% ({formatARS(taller.precio_sena)}) y adjuntá
          el comprobante.
        </p>
        <div className="mt-1 rounded-xl border border-dashed border-border/80 bg-muted/20 p-4">
          {upload.status === "idle" || upload.status === "error" ? (
            <>
              <label
                htmlFor="ins-comprobante"
                className="flex flex-col items-center gap-2 cursor-pointer"
              >
                <Upload className="h-6 w-6 text-muted-foreground" strokeWidth={1.5} />
                <span className="text-sm text-muted-foreground text-center">
                  Cliqueá para adjuntar o arrastrá acá
                  <br />
                  <span className="text-xs">JPG, PNG, PDF — máx 10 MB</span>
                </span>
                <input
                  id="ins-comprobante"
                  type="file"
                  ref={fileRef}
                  accept="image/jpeg,image/png,image/webp,image/heic,application/pdf"
                  className="sr-only"
                  onChange={handleFile}
                  disabled={submitState === "submitting"}
                />
              </label>
              {upload.status === "error" && (
                <p className="mt-2 text-xs text-red-600 text-center">{upload.message}</p>
              )}
            </>
          ) : upload.status === "uploading" ? (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Subiendo comprobante…
            </div>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4 shrink-0" strokeWidth={1.5} />
                <span className="truncate">{upload.fileName}</span>
              </div>
              <button
                type="button"
                onClick={removeFile}
                className="shrink-0 p-1 rounded hover:bg-muted transition text-muted-foreground hover:text-ink"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Alias: <span className="font-mono font-medium text-ink">{taller.pago_alias}</span>
          {" · "}CBU:{" "}
          <span className="font-mono text-ink">{taller.pago_cbu}</span>
          {" · "}{taller.pago_banco}
        </p>
      </div>

      {submitState === "error" && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Algo salió mal. Revisá los datos e intentá de nuevo.
        </div>
      )}

      <Button
        type="submit"
        disabled={submitState === "submitting" || upload.status === "uploading"}
        className="bg-ink text-amber hover:brightness-110 active:scale-[0.98] font-bold rounded-full py-6 text-base transition-all"
      >
        {submitState === "submitting" ? (
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Enviando…
          </span>
        ) : (
          "Reservar mi cupo"
        )}
      </Button>

      <p className="text-xs text-muted-foreground text-center">
        * Campos obligatorios
      </p>
    </form>
  );
}
