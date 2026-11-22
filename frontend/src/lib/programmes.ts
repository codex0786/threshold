// Short degree names, so two courses with the same name at one institute can be told apart.
const DEGREE_SHORT: [RegExp, string][] = [
  [/^Bachelor and Master of Technology \(Dual Degree\)$|^B\.\s?Tech\.? \+ M\.\s?Tech\.?\/MS \(Dual Degree\)$/, "B.Tech + M.Tech dual degree"],
  [/^Integrated B\.\s?Tech\.? and M\.\s?Tech\.?$|^Integrated Masters? (of|in) Technology$/, "Integrated B.Tech + M.Tech"],
  [/^Bachelor of Technology and MBA \(Dual Degree\)$|^Integrated B\.\s?Tech\.? and MBA$/, "B.Tech + MBA"],
  [/^Bachelor of Science and MBA \(Dual Degree\)$/, "BS + MBA"],
  [/^Bachelor of Science and Master of Science \(Dual Degree\)$|^Integrated Bachelor of Science-Master of Science$/, "BS + MS dual degree"],
  [/^Integrated Master of Science$/, "Integrated M.Sc"],
  [/^Bachelor of Technology$|^B\. Tech \/ B\. Tech \(Hons\.\)$/, "B.Tech"],
  [/^Bachelor of Science$/, "BS"],
  [/^Bachelor of Architecture$/, "B.Arch"],
  [/^Bachelor of Planning$/, "B.Plan"],
  [/^Bachelor of Design$/, "B.Des"],
];

export function degreeShort(degree: string | null | undefined): string | null {
  if (!degree) return null;
  return DEGREE_SHORT.find(([pattern]) => pattern.test(degree))?.[1] ?? degree;
}

/** "B.Tech, 4 years": the degree and its length, for a line under the course name. */
export function degreeLine(degree: string | null | undefined, years: number | null | undefined): string {
  return [degreeShort(degree), years ? `${years} years` : null].filter(Boolean).join(", ");
}

/** The course name with its degree when that isn't a plain 4-year B.Tech, so labels stay unique in lists. */
export function programmeLabel(name: string, degree?: string | null, years?: number | null): string {
  const short = degreeShort(degree);
  if (!short || (short === "B.Tech" && (years ?? 4) === 4) || name.toLowerCase().includes(short.toLowerCase())) return name;
  return `${name} (${degreeLine(degree, years)})`;
}
