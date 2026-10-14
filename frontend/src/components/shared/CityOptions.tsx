// City <option>s grouped under their state (and "Delhi NCR" for the capital region), so a
// long list is easy to scan. The server sends them in display order (/api/meta).
export type CityOption = { name: string; state: string; group?: string };

export function CityOptions({ cities }: { cities: CityOption[] }) {
  const groups = new Map<string, string[]>();
  for (const c of cities) {
    const g = c.group ?? c.state;
    groups.set(g, [...(groups.get(g) ?? []), c.name]);
  }
  return (
    <>
      {[...groups.entries()].map(([group, names]) => (
        <optgroup key={group} label={group}>
          {names.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}
