import * as React from "react";
import { cn } from "@/lib/utils";
import { buttonVariants, type ButtonProps } from "./button";

export type IconButtonSize = "xs" | "sm" | "md" | "lg";

// xs=28px tabla densa, sm=32px toolbars, md=36px default (HIG desktop), lg=44px tap target mobile
const SIZE: Record<IconButtonSize, string> = {
  xs: "h-7 w-7",
  sm: "h-8 w-8",
  md: "",
  lg: "h-11 w-11",
};

export interface IconButtonProps extends Omit<
  React.ButtonHTMLAttributes<HTMLButtonElement>,
  "children"
> {
  /** Obligatorio: usado por screen readers en lugar del texto visible. */
  "aria-label": string;
  children: React.ReactNode;
  variant?: ButtonProps["variant"];
  size?: IconButtonSize;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, variant = "ghost", size = "md", disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size: "icon" }), SIZE[size], className)}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  ),
);
IconButton.displayName = "IconButton";
