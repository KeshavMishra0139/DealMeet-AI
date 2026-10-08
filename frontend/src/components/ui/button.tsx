import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background,color,box-shadow,transform,opacity] duration-200 ease-[var(--ease-soft)] disabled:pointer-events-none disabled:opacity-50 active:translate-y-px [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-signature-strong text-white shadow-[0_8px_24px_-10px_rgb(219_39_119/0.6)] hover:shadow-[0_10px_30px_-8px_rgb(219_39_119/0.7)] hover:brightness-110",
        accent: "bg-accent text-accent-fg hover:bg-accent-strong",
        secondary: "bg-surface-2 text-fg hover:bg-surface-3 border border-line",
        outline: "border border-line-strong bg-transparent text-fg hover:bg-surface-2",
        ghost: "bg-transparent text-fg-2 hover:bg-surface-2 hover:text-fg",
        danger: "bg-danger-soft text-danger hover:brightness-110",
        success: "bg-success-soft text-success hover:brightness-110",
        link: "h-auto px-0 text-accent underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 rounded-lg px-3 text-[13px]",
        md: "h-10 rounded-xl px-4 text-sm",
        lg: "h-12 rounded-2xl px-6 text-[15px]",
        icon: "size-10 rounded-xl",
        "icon-sm": "size-8 rounded-lg",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {asChild ? (
          children
        ) : (
          <>
            {loading && <Loader2 className="animate-spin" aria-hidden />}
            {children}
          </>
        )}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
