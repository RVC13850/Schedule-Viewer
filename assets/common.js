// Shared helpers: data loading, time math, formatting.

const DATA_URL = new URL("../data/schedule.json", import.meta.url);

export async function loadSchedule() {
  const res = await fetch(DATA_URL, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load schedule data (HTTP ${res.status})`);
  return res.json();
}

/** Minutes past midnight for an "HH:MM" string. */
export function toMinutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

/** 870 -> "2:30 PM" */
export function formatTime(minutes) {
  const m = ((minutes % 1440) + 1440) % 1440;
  const h24 = Math.floor(m / 60);
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  return `${h12}:${String(m % 60).padStart(2, "0")} ${h24 < 12 ? "AM" : "PM"}`;
}

/** 95 -> "1 hr 35 min" */
export function formatDuration(minutes) {
  const mins = Math.max(0, Math.round(minutes));
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h && m) return `${h} hr ${m} min`;
  if (h) return `${h} hr`;
  return `${m} min`;
}

/**
 * "Now" evaluated in the schedule's own timezone, so the dashboard is correct
 * no matter where the viewer is.
 */
export function nowIn(timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());

  const get = (type) => parts.find((p) => p.type === type)?.value ?? "";
  const hour = Number(get("hour")) % 24;
  const minute = Number(get("minute"));
  const second = Number(get("second"));

  return {
    weekday: get("weekday"),
    dateLabel: `${get("weekday")}, ${get("month")} ${get("day")}`,
    minutes: hour * 60 + minute,
    seconds: second,
    clock: formatTime(hour * 60 + minute),
  };
}

export function initials(name) {
  return name
    .split(/[\s-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

/** Small org logo for a person, or "" if there isn't one. */
export function orgIcon(data, person) {
  const src = data.icons?.[person];
  if (!src) return "";
  const label = data.schools?.[person] || "";
  return `<img class="org" src="./${escapeHtml(src)}" alt="${escapeHtml(label)}" title="${escapeHtml(label)}" />`;
}

export function eventsFor(data, day, person) {
  return (data.days[day] || [])
    .filter((e) => e.person === person)
    .sort((a, b) => a.startMinutes - b.startMinutes);
}

/** Where someone stands in their day at `minutes`. */
export function personStatus(events, minutes) {
  const current = events.find((e) => minutes >= e.startMinutes && minutes < e.endMinutes) || null;
  const next = events.find((e) => e.startMinutes > minutes) || null;
  const remaining = events.filter((e) => e.endMinutes > minutes).length;
  return { current, next, remaining, total: events.length };
}

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

export function renderNav(activeDay, data) {
  const links = [
    `<a href="./index.html"${activeDay ? "" : ' class="active"'}>Live Dashboard</a>`,
    ...data.dayOrder.map((d) => {
      const active = d === activeDay ? ' class="active"' : "";
      return `<a href="./day.html?day=${encodeURIComponent(d)}"${active}>${escapeHtml(d)}</a>`;
    }),
  ];
  return links.join("");
}

export function renderFooter(data) {
  const generated = new Date(data.generatedAt);
  return `Data synced ${generated.toLocaleString()} &middot; times shown in ${escapeHtml(data.timezone)} &middot;
    <a href="${escapeHtml(data.source)}" target="_blank" rel="noopener noreferrer">source spreadsheet</a>`;
}
