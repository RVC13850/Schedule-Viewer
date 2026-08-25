import {
  loadSchedule, nowIn, toMinutes, formatTime, formatDuration, orgIcon,
  eventsFor, escapeHtml, renderNav, renderFooter,
} from "./common.js";

const SLOT_PX = 26;

const els = {
  title: document.getElementById("title"),
  sub: document.getElementById("sub"),
  clock: document.getElementById("clock"),
  date: document.getElementById("date"),
  nav: document.getElementById("nav"),
  search: document.getElementById("search"),
  board: document.getElementById("board"),
  daylist: document.getElementById("daylist"),
  footer: document.getElementById("footer"),
};

let data = null;
let day = null;

function visiblePeople() {
  const q = els.search.value.trim().toLowerCase();
  if (!q) return data.people;
  const terms = q.split(/[,\s]+/).filter(Boolean);
  const matched = data.people.filter((p) =>
    terms.some((t) => p.toLowerCase().includes(t)
      || eventsFor(data, day, p).some((e) => `${e.title} ${e.location}`.toLowerCase().includes(t))));
  return matched.length ? matched : data.people;
}

function renderBoard(people, now) {
  const start = toMinutes(data.gridStart);
  const end = toMinutes(data.gridEnd);
  const slots = Math.max(1, (end - start) / data.slotMinutes);

  els.board.style.gridTemplateColumns = `78px repeat(${people.length}, minmax(134px, 1fr))`;
  els.board.style.gridTemplateRows = `auto repeat(${slots}, ${SLOT_PX}px)`;

  const parts = [`<div class="hcell corner">Time</div>`];
  for (const p of people) parts.push(`<div class="hcell">${orgIcon(data, p)}${escapeHtml(p)}</div>`);

  for (let i = 0; i < slots; i += 1) {
    const minutes = start + i * data.slotMinutes;
    const isHour = minutes % 60 === 0;
    parts.push(`<div class="tcell${isHour ? " hour" : ""}" style="grid-row:${i + 2};grid-column:1">${
      isHour ? formatTime(minutes) : ""}</div>`);
    for (let c = 0; c < people.length; c += 1) {
      parts.push(`<div class="slot${isHour ? " hour" : ""}" style="grid-row:${i + 2};grid-column:${c + 2}"></div>`);
    }
  }

  people.forEach((person, idx) => {
    for (const e of eventsFor(data, day, person)) {
      const offset = (e.startMinutes - start) / data.slotMinutes;
      const length = (e.endMinutes - e.startMinutes) / data.slotMinutes;
      const row = Math.floor(offset) + 2;
      const span = Math.max(1, Math.ceil(offset + length) - Math.floor(offset));
      parts.push(`<div class="ev${length <= 1 ? " tiny" : length <= 2 ? " short" : ""}" style="grid-column:${idx + 2};grid-row:${row} / span ${span};margin-top:${
        ((offset % 1) * SLOT_PX + 1).toFixed(1)}px;height:${(length * SLOT_PX - 2).toFixed(1)}px"
        title="${escapeHtml(person)} — ${escapeHtml(e.title)} ${formatTime(e.startMinutes)}–${formatTime(e.endMinutes)}">
        <b>${escapeHtml(e.title)}</b>
        ${e.location ? `<small>${escapeHtml(e.location)}</small>` : ""}
        <span class="t">${formatTime(e.startMinutes)}&ndash;${formatTime(e.endMinutes)}${
          e.endEstimated ? " (est.)" : ""}</span>
      </div>`);
    }
  });

  if (now.weekday === day && now.minutes >= start && now.minutes <= end) {
    const offset = (now.minutes - start) / data.slotMinutes;
    parts.push(`<div class="nowline" style="grid-row:${Math.floor(offset) + 2};margin-top:${
      (offset % 1) * SLOT_PX}px"></div>`);
  }

  els.board.innerHTML = parts.join("");
}

function renderList(people) {
  els.daylist.innerHTML = people.map((person) => {
    const events = eventsFor(data, day, person);
    const items = events.length
      ? `<ul>${events.map((e) => `<li>
            <time>${formatTime(e.startMinutes)} &ndash; ${formatTime(e.endMinutes)}</time>
            <span><strong>${escapeHtml(e.title)}</strong>${e.location ? ` &middot; ${escapeHtml(e.location)}` : ""}
            <br /><span class="empty">${formatDuration(e.endMinutes - e.startMinutes)}${
              e.endEstimated ? " (end time not recorded)" : ""}</span></span>
          </li>`).join("")}</ul>`
      : `<p class="empty">Nothing scheduled.</p>`;
    return `<div class="person-block"><h3>${orgIcon(data, person)}${escapeHtml(person)}</h3>${items}</div>`;
  }).join("");
}

function render() {
  const now = nowIn(data.timezone);
  els.clock.textContent = now.clock;
  els.date.textContent = now.dateLabel;

  const people = visiblePeople();
  const count = (data.days[day] || []).length;
  els.title.textContent = `${day} Schedule`;
  document.title = `${day} Schedule · Schedule Viewer`;
  els.sub.innerHTML = `${count} class block${count === 1 ? "" : "s"} across ${data.people.length} people${
    now.weekday === day ? " &middot; <strong>today</strong>" : ""}`;

  renderBoard(people, now);
  renderList(people);
}

(async function start() {
  try {
    data = await loadSchedule();
  } catch (err) {
    els.board.innerHTML = `<div class="err">${escapeHtml(err.message)}<br />
      If you are opening this file directly, serve it instead: <code>python3 -m http.server</code></div>`;
    return;
  }

  const requested = new URLSearchParams(location.search).get("day");
  const match = data.dayOrder.find((d) => d.toLowerCase() === (requested || "").toLowerCase());
  day = match || data.dayOrder.find((d) => d === nowIn(data.timezone).weekday) || data.dayOrder[0];

  els.nav.innerHTML = renderNav(day, data);
  els.footer.innerHTML = renderFooter(data);
  els.search.addEventListener("input", render);

  render();
  setInterval(render, 30000);
})();
