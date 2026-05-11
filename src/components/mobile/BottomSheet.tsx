import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerTitle,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** Max height as a Tailwind class, default "max-h-[85vh]" */
  maxH?: string;
  /** Show close button in header */
  showClose?: boolean;
};

export function BottomSheet({
  open,
  onOpenChange,
  title,
  children,
  footer,
  maxH = "max-h-[85vh]",
  showClose = false,
}: Props) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        className={cn(
          "flex flex-col rounded-t-2xl p-0",
          maxH,
        )}
      >
        {title && (
          <div className="sticky top-0 z-10 shrink-0 border-b hairline bg-background/95 px-4 py-3 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <DrawerTitle className="font-display text-lg">{title}</DrawerTitle>
              {showClose && (
                <DrawerClose className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-ink">
                  <X className="h-4 w-4" />
                </DrawerClose>
              )}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>

        {footer && (
          <div
            className="sticky bottom-0 z-10 shrink-0 border-t hairline bg-background/95 px-4 py-3 backdrop-blur-xl"
            style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
          >
            {footer}
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}
