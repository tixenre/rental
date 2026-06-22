import { Drawer, DrawerContent, DrawerTitle } from "@/design-system/ui/drawer";
import { cn } from "@/lib/utils";

type Action = {
  label: string;
  icon?: React.ReactNode;
  variant?: "default" | "destructive";
  onClick: () => void;
};

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title?: string;
  actions: Action[];
};

export function ActionMenu({ open, onOpenChange, title, actions }: Props) {
  const normal = actions.filter((a) => a.variant !== "destructive");
  const destructive = actions.filter((a) => a.variant === "destructive");

  function handle(action: Action) {
    onOpenChange(false);
    action.onClick();
  }

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="rounded-t-2xl p-0">
        {title && (
          <div className="border-b hairline px-4 py-3">
            <DrawerTitle className="text-center text-sm font-medium text-muted-foreground">
              {title}
            </DrawerTitle>
          </div>
        )}

        <div
          className="pb-2"
          style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom))" }}
        >
          {normal.map((action, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handle(action)}
              className="flex h-14 w-full items-center gap-3 px-5 text-left transition hover:bg-muted active:bg-muted"
            >
              {action.icon && <span className="shrink-0 text-muted-foreground">{action.icon}</span>}
              <span className="font-medium">{action.label}</span>
            </button>
          ))}

          {destructive.length > 0 && (
            <>
              {normal.length > 0 && <div className="mx-4 border-t hairline" />}
              {destructive.map((action, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handle(action)}
                  className="flex h-14 w-full items-center gap-3 px-5 text-left transition hover:bg-destructive/5 active:bg-destructive/10"
                >
                  {action.icon && <span className="shrink-0 text-destructive">{action.icon}</span>}
                  <span className="font-medium text-destructive">{action.label}</span>
                </button>
              ))}
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
