import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";
import { buttonVariants } from "@/design-system/ui/button";

/**
 * useConfirm — confirmación destructiva como promesa, sobre el AlertDialog del DS.
 *
 * Reemplaza los `window.confirm()` / `window.prompt()` nativos (sin focus-trap,
 * sin tokens, fuera del look del back-office). Una sola forma del "¿estás seguro?".
 *
 *   const confirm = useConfirm();
 *   if (await confirm({ title: "¿Borrar caja?", danger: true })) { … }
 *
 * Montá `<ConfirmProvider>` una vez en AdminLayout; el hook funciona en cualquier
 * descendiente.
 */
export type ConfirmOptions = {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Acción destructiva → botón en tono destructive. */
  danger?: boolean;
};

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(o);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const settle = (result: boolean) => {
    resolver.current?.(result);
    resolver.current = null;
    setOpts(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <AlertDialog
        open={!!opts}
        onOpenChange={(open) => {
          if (!open) settle(false);
        }}
      >
        {opts && (
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{opts.title}</AlertDialogTitle>
              {opts.description && (
                <AlertDialogDescription>{opts.description}</AlertDialogDescription>
              )}
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => settle(false)}>
                {opts.cancelLabel ?? "Cancelar"}
              </AlertDialogCancel>
              <AlertDialogAction
                className={opts.danger ? buttonVariants({ variant: "destructive" }) : undefined}
                onClick={() => settle(true)}
              >
                {opts.confirmLabel ?? "Confirmar"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        )}
      </AlertDialog>
    </ConfirmContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- hook + provider conviven a propósito (patrón context); el provider se monta una vez en AdminLayout
export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm debe usarse dentro de <ConfirmProvider>");
  return ctx;
}
