import { BarChart3, IndianRupee, Users } from "lucide-react";
import { Switch } from "@/components/ui/form";
import type { Scopes } from "@/lib/market-types";

const ROWS: { key: keyof Scopes; label: string; hint: string; icon: typeof Users }[] = [
  { key: "stats", label: "Reach and engagement stats", hint: "Median views, saves and shares, posting pace", icon: BarChart3 },
  { key: "demographics", label: "Audience demographics", hint: "Ages, gender split, cities and languages", icon: Users },
  { key: "rate_card", label: "Your rate card", hint: "The rate you usually quote", icon: IndianRupee },
];

/** Per-lister data scopes. Used when applying, and in the consent ledger. */
export function ScopePicker({
  value,
  onChange,
  disabled,
  compact = false,
}: {
  value: Scopes;
  onChange: (v: Scopes) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className="divide-y divide-line rounded-2xl border border-line">
      {ROWS.map((r) => (
        <label key={r.key} className="flex cursor-pointer items-center gap-3 px-3.5 py-3">
          <r.icon className="size-4 shrink-0 text-muted" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium">{r.label}</span>
            {!compact && <span className="block text-xs text-muted">{r.hint}</span>}
          </span>
          <Switch
            checked={value[r.key]}
            disabled={disabled}
            onCheckedChange={(v) => onChange({ ...value, [r.key]: v })}
            aria-label={r.label}
          />
        </label>
      ))}
    </div>
  );
}
