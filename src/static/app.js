const margin = { top: 24, right: 30, bottom: 40, left: 64 };
const width = 900;
const height = 450;

const MAX_SELECTED = 8;

const METRICS = {
  co2_per_capita: "CO₂ per capita (tonnes per person)",
  co2: "CO₂ emissions (million tonnes)",
  total_ghg: "Total greenhouse gas emissions (million tonnes CO₂e)",
  population: "Population",
  gdp: "GDP (international-$)",
};

const state = {
  metric: "co2_per_capita",
  selected: ["Germany", "France", "United States", "China", "Ghana"],
};

const cache = new Map(); // entity name -> Promise of its rows
const color = d3.scaleOrdinal(d3.schemeTableau10); 
let validNames = new Set();
let renderToken = 0;

// ---------- fetch data ----------

async function fetchJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`API error ${response.status} for ${path}`);
  return response.json();
}

function loadEntity(name) {
  if (!cache.has(name)) {
    const promise = fetchJSON(`/emissions/${encodeURIComponent(name)}`).catch(
      (err) => {
        cache.delete(name); // don't cache failures
        throw err;
      }
    );
    cache.set(name, promise);
  }
  return cache.get(name);
}

// ---------- chart skeleton: built once, updated many times ----------

const svg = d3
  .select("#chart")
  .append("svg")
  .attr("viewBox", `0 0 ${width} ${height}`);

const x = d3.scaleLinear().range([margin.left, width - margin.right]);
const y = d3.scaleLinear().range([height - margin.bottom, margin.top]);

const gx = svg
  .append("g")
  .attr("transform", `translate(0,${height - margin.bottom})`);
const gy = svg.append("g").attr("transform", `translate(${margin.left},0)`);
const yLabel = svg
  .append("text")
  .attr("x", margin.left)
  .attr("y", 14)
  .attr("font-size", 12)
  .attr("fill", "#666");

const zeroLine = svg
  .append("line")
  .attr("x1", margin.left)
  .attr("x2", width - margin.right)
  .attr("y1", height - margin.bottom)
  .attr("y2", height - margin.bottom)
  .attr("stroke", "#999")
  .attr("stroke-dasharray", "4 3");

const lines = svg.append("g");

// ---------- UI helpers ----------

function say(text, isError = false) {
  d3.select("#message").classed("error", isError).text(text);
}

function renderChips() {
  d3.select("#chips")
    .selectAll("li")
    .data(state.selected, (d) => d)
    .join((enter) => {
      const li = enter.append("li").attr("class", "chip");
      li.append("span")
        .attr("class", "swatch")
        .style("background", (d) => color(d));
      li.append("span").text((d) => d);
      li.append("button")
        .attr("type", "button")
        .attr("aria-label", (d) => `Remove ${d}`)
        .text("×")
        .on("click", (event, d) => removeEntity(d));
      return li;
    });
}

function addEntity(name) {
  if (state.selected.includes(name)) return;
  if (state.selected.length >= MAX_SELECTED) {
    say(`Up to ${MAX_SELECTED} lines at once. Remove one first.`);
    return;
  }
  state.selected.push(name);
  renderChips();
  render();
}

function removeEntity(name) {
  state.selected = state.selected.filter((n) => n !== name);
  renderChips();
  render();
}

// ---------- drawing ----------

async function render() {
  const token = ++renderToken; // ignore results from superseded renders
  const key = state.metric;

  let results;
  try {
    results = await Promise.all(
      state.selected.map(async (name) => ({
        name,
        values: await loadEntity(name),
      }))
    );
  } catch (err) {
    if (token === renderToken) say(`Could not load data: ${err.message}`, true);
    return;
  }
  if (token !== renderToken) return;

  const hasData = (s) => s.values.some((d) => d[key] != null);
  const drawable = results.filter(hasData);
  const empty = results.filter((s) => !hasData(s)).map((s) => s.name);
  say(
    empty.length
      ? `No ${METRICS[key]} data for: ${empty.join(", ")}`
      : ""
  );

  const t = svg.transition().duration(500);

  if (drawable.length === 0) {
    lines.selectAll("path").remove();
    return;
  }

  const points = drawable.flatMap((s) => s.values).filter((d) => d[key] != null);
  x.domain(d3.extent(points, (d) => d.year));
  const [lo, hi] = d3.extent(points, (d) => d[key]);
  y.domain([Math.min(0, lo), Math.max(0, hi)]).nice();

  gx.transition(t).call(d3.axisBottom(x).tickFormat(d3.format("d")));
  gy.transition(t).call(d3.axisLeft(y).ticks(6).tickFormat(d3.format("~s")));
  zeroLine.transition(t).attr("y1", y(0)).attr("y2", y(0));
  yLabel.text(METRICS[key]);

  const line = d3
    .line()
    .defined((d) => d[key] != null)
    .x((d) => x(d.year))
    .y((d) => y(d[key]));

  lines
    .selectAll("path")
    .data(drawable, (d) => d.name)
    .join(
      (enter) =>
        enter
          .append("path")
          .attr("fill", "none")
          .attr("stroke-width", 2)
          .attr("stroke", (d) => color(d.name))
          .attr("d", (d) => line(d.values))
          .attr("opacity", 0)
          .call((e) => e.transition(t).attr("opacity", 1)),
      (update) => update.attr("d", (d) => line(d.values)),
      (exit) => exit.call((e) => e.transition(t).attr("opacity", 0).remove())
    );
}

// ---------- start-up ----------

async function init() {
  const nameOf = (item) => (typeof item === "string" ? item : item.country);
  const [countries, aggregates] = await Promise.all([
    fetchJSON("/countries"),
    fetchJSON("/aggregates"),
  ]);
  const names = [...countries, ...aggregates].map(nameOf).sort(d3.ascending);
  validNames = new Set(names);

  d3.select("#entity-list")
    .selectAll("option")
    .data(names)
    .join("option")
    .attr("value", (d) => d);

  d3.select("#metric")
    .selectAll("option")
    .data(Object.entries(METRICS))
    .join("option")
    .attr("value", (d) => d[0])
    .text((d) => d[1]);
  d3.select("#metric")
    .property("value", state.metric)
    .on("change", (event) => {
      state.metric = event.target.value;
      render();
    });

  const input = d3.select("#entity-input");
  input.on("change", () => {
    const name = input.property("value").trim();
    input.property("value", "");
    if (!name) return;
    if (!validNames.has(name)) {
      say(`"${name}" isn't in the dataset. Pick a name from the list.`, true);
      return;
    }
    addEntity(name);
  });

  state.selected = state.selected.filter((n) => validNames.has(n));
  renderChips();
  await render();
}

init().catch((err) => say(`Could not start: ${err.message}`, true));