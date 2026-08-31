import {
  loadSchedule, nowIn, formatTime, formatDuration, initials, orgIcon,
  eventsFor, personStatus, escapeHtml, renderNav, renderFooter,
} from "./common.js?v=2";

const SOON_MINUTES = 30;

const els = {
  sub: document.getElementById("sub"),
  clock: document.getElementById("clock"),
  date: document.getElementById("date"),
  nav: document.getElementById("nav"),
  search: document.getElementById("search"),
  busyOnly: document.getElementById("busy-only"),
  summary: document.getElementById("summary"),
  cards: document.getElementById("cards"),
  footer: document.getElementById("footer"),
};

let data = null;

function activeDay(weekday) {
  return data.dayOrder.includes(weekday) ? weekday : null;
}

function cardHtml(person, events, now, day) {
  const { current, next } = personStatus(events, now.minutes);
  const working = current?.kind === "work";
  const state = current ? "busy" : next && next.startMinutes - now.minutes <= SOON_MINUTES ? "soon" : "idle";

  let body;
  if (current) {
    const left = current.endMinutes - now.minutes;
    const pct = Math.min(100, Math.max(0,
      ((now.minutes - current.startMinutes) / (current.endMinutes - current.startMinutes)) * 100));
    const endText = current.endEstimated
      ? `<span class="ends est">Scheduled end not recorded &mdash; assuming <strong>${formatTime(current.endMinutes)}</strong></span>`
      : `<span class="ends">${working ? "Off at" : "Ends at"} <strong>${formatTime(current.endMinutes)}</strong> &middot; ${formatDuration(left)} left</span>`;
    body = `
      <div class="now-line">${escapeHtml(current.title)}</div>
      <div class="now-meta">${current.location ? escapeHtml(current.location) + " &middot; " : ""}${formatTime(current.startMinutes)} &ndash; ${formatTime(current.endMinutes)}</div>
      ${endText}
      <div class="bar"><i style="width:${pct.toFixed(1)}%"></i></div>`;
  } else if (next) {
    body = `
      <div class="now-line">Free right now</div>
      <div class="now-meta">Next ${next.kind === "work" ? "shift" : "class"} starts in ${formatDuration(next.startMinutes - now.minutes)}</div>`;
  } else if (events.length) {
    body = `
      <div class="now-line">Done for the day</div>
      <div class="now-meta">Last ${events[events.length - 1].kind === "work" ? "shift" : "class"} ended at ${formatTime(events[events.length - 1].endMinutes)}</div>`;
  } else {
    body = `
      <div class="now-line">No classes ${day ? `on ${escapeHtml(day)}` : "scheduled"}</div>
      <div class="now-meta">Nothing on the timetable</div>`;
  }

  const upNext = next
    ? `<div class="up-next"><span class="k">Up next</span>
         <span><strong>${escapeHtml(next.title)}</strong>${next.location ? " &middot; " + escapeHtml(next.location) : ""}
         <br /><span class="next-line">${formatTime(next.startMinutes)} &ndash; ${formatTime(next.endMinutes)}</span></span></div>`
    : "";

  const rest = events.length
    ? `<ul class="rest">${events.map((e) => `
        <li class="${e.endMinutes <= now.minutes ? "done" : ""}">
          <span>${escapeHtml(e.title)}${e.location ? ` <em>${escapeHtml(e.location)}</em>` : ""}</span>
          <span>${formatTime(e.startMinutes)}&ndash;${formatTime(e.endMinutes)}</span>
        </li>`).join("")}</ul>`
    : "";

  const badge = state === "busy"
    ? (working ? "Working" : "In class")
    : { soon: "Starting soon", idle: events.length ? "Free" : "No classes" }[state];

  return `<article class="card is-${working ? "work" : state}" data-search="${escapeHtml((person + " " + events.map((e) => e.title + " " + e.location).join(" ")).toLowerCase())}" data-busy="${state === "busy"}">
    <div class="card-head">
      <div class="avatar">${escapeHtml(initials(person))}</div>
      <div class="name">${escapeHtml(person)}<span class="school">${orgIcon(data, person)}${escapeHtml(data.schools?.[person] || "")}</span></div>
      <div class="badge ${working ? "work" : state === "idle" ? "" : state}">${badge}</div>
    </div>
    <div class="card-body">
      ${body}
      ${upNext ? `<div class="divider"></div>${upNext}` : ""}
    </div>
    ${rest ? `<div class="card-foot"><div class="divider"></div>${rest}</div>` : ""}
  </article>`;
}

function applyFilters() {
  const q = els.search.value.trim().toLowerCase();
  const busyOnly = els.busyOnly.checked;
  let shown = 0;
  for (const card of els.cards.querySelectorAll(".card")) {
    const matches = (!q || card.dataset.search.includes(q)) && (!busyOnly || card.dataset.busy === "true");
    card.hidden = !matches;
    if (matches) shown += 1;
  }
  const none = els.cards.querySelector(".no-results");
  if (none) none.remove();
  if (!shown) {
    els.cards.insertAdjacentHTML("beforeend", `<p class="empty no-results">No one matches that filter.</p>`);
  }
}

function render() {
  const now = nowIn(data.timezone);
  const day = activeDay(now.weekday);

  els.clock.textContent = now.clock;
  els.date.textContent = now.dateLabel;
  els.sub.innerHTML = day
    ? `Showing <strong>${escapeHtml(day)}</strong> &middot; ${data.people.length} people tracked`
    : `No classes on ${escapeHtml(now.weekday)} &middot; pick a weekday below`;

  const rows = data.people.map((person) => {
    const events = day ? eventsFor(data, day, person) : [];
    return { person, events, status: personStatus(events, now.minutes) };
  });

  // Busy first, then starting soon, then free, then people with nothing scheduled.
  const rank = (r) => (r.status.current ? 0 : r.status.next
    ? (r.status.next.startMinutes - now.minutes <= SOON_MINUTES ? 1 : 2)
    : r.events.length ? 3 : 4);
  rows.sort((a, b) => rank(a) - rank(b));

  const inClass = rows.filter((r) => r.status.current && r.status.current.kind !== "work").length;
  const working = rows.filter((r) => r.status.current?.kind === "work").length;
  const soon = rows.filter((r) => !r.status.current && r.status.next
    && r.status.next.startMinutes - now.minutes <= SOON_MINUTES).length;
  const free = rows.length - inClass - working - soon;

  els.summary.innerHTML = `
    <div class="stat"><div class="n">${inClass}</div><div class="l">In class</div></div>
    <div class="stat"><div class="n">${working}</div><div class="l">Working</div></div>
    <div class="stat"><div class="n">${soon}</div><div class="l">Starting soon</div></div>
    <div class="stat"><div class="n">${free}</div><div class="l">Free</div></div>`;

  els.cards.innerHTML = rows.map((r) => cardHtml(r.person, r.events, now, day)).join("");
  applyFilters();
}

(async function start() {
  try {
    data = await loadSchedule();
  } catch (err) {
    document.getElementById("cards").innerHTML =
      `<div class="err">${escapeHtml(err.message)}<br />
       If you are opening this file directly, serve it instead: <code>python3 -m http.server</code></div>`;
    return;
  }

  els.nav.innerHTML = renderNav(null, data);
  els.footer.innerHTML = renderFooter(data);
  els.search.addEventListener("input", applyFilters);
  els.busyOnly.addEventListener("change", applyFilters);

  render();
  setInterval(render, 15000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) render(); });
})();
