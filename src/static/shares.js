(() => {
  const SIZE = 420;
  const RADIUS = 190;
  const INNER = 108; // set to 0 for a plain pie
  const TOP_COUNTRIES = 8;
  const MIN_TOP_SHARE = 0.005; // top level: slices under 0.5% merge into "Other"
  const OTHER_COLOUR = "#c8c8c8";

  const CONTINENT_COLOURS = {
    Asia: "#4e79a7",
    Europe: "#f28e2b",
    "North America": "#e15759",
    "South America": "#76b7b2",
    Africa: "#59a14f",
    Oceania: "#edc948",
    Antarctica: "#b07aa1",
    Unassigned: "#9c755f",
    "International aviation": "#7f7f7f",
    "Interational shipping": "#9c755f",
    Unallocated: "#e3e3e3",
  };
  const colourFor = (name) => CONTINENT_COLOURS[name] ?? "#999999";

  const fmtMt = (v) => (v >= 10 ? d3.format(",.0f")(v) : d3.format(",.2f")(v));
  const fmtPct = (v) => (v < 0.01 ? d3.format(".2%")(v) : d3.format(".1%")(v));

  const state = { year: null, drill: null };
  const cache = new Map();
  let token = 0;

  const slider = document.getElementById("shares-year");
  const yearLabel = document.getElementById("shares-year-label");
  const backButton = document.getElementById("shares-back");
  const figure = document.getElementById("shares-figure");
  const tip = d3.select("#shares-tooltip");

  // ---------- data ----------

  function load(year) {
    const key = year ?? "latest";
    if (!cache.has(key)) {
      const url = year == null ? "/shares" : `/shares?year=${year}`;
      const promise = fetch(url)
        .then((r) => {
          if (!r.ok) throw new Error(`no data for ${year ?? "the latest year"}`);
          return r.json();
        })
        .catch((err) => {
          cache.delete(key);
          throw err;
        });
      cache.set(key, promise);
    }
    return cache.get(key);
  }

  // Keep the biggest items as slices and merge the rest into "Other".
  // `rows` is the full list for the table: nothing is hidden there.
  function group(items, total, { minShare = 0, maxSlices = Infinity } = {}) {
    const sorted = [...items].sort((a, b) => b.value - a.value);
    const keep = [];
    const rest = [];
    for (const item of sorted) {
      if (item.value / total >= minShare && keep.length < maxSlices) {
        keep.push(item);
      } else {
        rest.push(item);
      }
    }
    if (rest.length === 1) keep.push(rest.pop()); // "Other (1)" is pointless

    const slices = [...keep];
    if (rest.length > 1) {
      slices.push({
        key: "__other",
        label: `Other (${rest.length})`,
        value: d3.sum(rest, (d) => d.value),
        color: OTHER_COLOUR,
        drill: false,
        members: rest.length,
      });
    }
    const merged = new Set(rest.map((d) => d.key));
    const rows = sorted.map((d) => ({
      ...d,
      swatch: merged.has(d.key) ? OTHER_COLOUR : d.color,
    }));
    return { slices, rows };
  }

  // ---------- models: what to show at each level ----------

  function topModel(data) {
    const world = data.world_total;
    const items = data.continents.map((c) => ({
      key: c.name,
      label: c.name,
      value: c.value,
      color: colourFor(c.name),
      drill: true,
    }));
    if (data.international_transport > 0) {
      items.push({
        key: "International aviation",
        label: "International aviation",
        value: data.international_transport,
        color: colourFor("International aviation"),
        drill: false,
      });
    }

    if (data.international_shipping > 0) {
      items.push({
        key: "International shipping",
        label: "International shipping",
        value: data.international_shipping,
        color: colourFor("International shipping"),
        drill: false,
      });
    }

    if (data.unallocated > 0) {
      items.push({
        key: "Unallocated",
        label: "Unallocated",
        value: data.unallocated,
        color: colourFor("Unallocated"),
        drill: false,
      });
    }
    const { slices, rows } = group(items, world, { minShare: MIN_TOP_SHARE });

    const gap = data.unallocated / world;
    let note = "";
    if (gap <= -0.01) {
      note = `Country and transport figures add up to ${fmtPct(-gap)} more than the reported world total.`;
    } else if (gap >= 0.01) {
      note = `${fmtPct(gap)} of the world total is not assigned to a country with a continent (shown as "Unallocated"). Earlier years may include former states without ISO codes.`;
    }

    return {
      total: world,
      slices,
      rows,
      title: `Share of global fossil CO₂ emissions, ${data.year}`,
      sub: `World total: ${fmtMt(world)} million tonnes.`,
      centre: ["World", `${fmtMt(world)} Mt`],
      note,
    };
  }

  function drillModel(continent, data) {
    const base = colourFor(continent.name);
    const items = [...continent.countries]
      .sort((a, b) => b.value - a.value)
      .map((c, i) => ({
        key: c.name,
        label: c.name,
        value: c.value,
        color: d3.interpolateRgb(base, "#ffffff")(Math.min(0.08 + 0.07 * i, 0.6)),
        drill: false,
      }));
    const { slices, rows } = group(items, continent.value, {
      maxSlices: TOP_COUNTRIES,
    });
    const worldShare = fmtPct(continent.value / data.world_total);
    return {
      total: continent.value,
      slices,
      rows,
      title: `${continent.name}: each country's share of the continent's CO₂, ${data.year}`,
      sub: `${continent.name} emits ${fmtMt(continent.value)} million tonnes, ${worldShare} of the world total.`,
      centre: [continent.name, `${worldShare} of world`],
      note: "",
    };
  }

  // ---------- chart skeleton: built once ----------

  const svg = d3
    .select("#shares-chart")
    .append("svg")
    .attr("viewBox", `0 0 ${SIZE} ${SIZE}`)
    .attr("role", "img");
  const g = svg.append("g").attr("transform", `translate(${SIZE / 2},${SIZE / 2})`);
  const arcs = g.append("g");
  const centreTop = g
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", -4)
    .attr("font-size", 20)
    .attr("font-weight", 600);
  const centreBottom = g
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", 18)
    .attr("font-size", 13)
    .attr("fill", "#666");

  const pie = d3.pie().sort(null).value((d) => d.value).padAngle(0.008);
  const arc = d3
    .arc()
    .innerRadius(INNER)
    .outerRadius(RADIUS)
    .cornerRadius(2);

  // ---------- UI helpers ----------

  function say(text, isError = false) {
    d3.select("#shares-message").classed("error", isError).text(text);
  }

  function drillInto(name) {
    state.drill = name;
    hideTip();
    render();
  }

  function showTip(event, d, total) {
    const [px, py] = d3.pointer(event, figure);
    tip.attr("hidden", null).style("left", `${px + 14}px`).style("top", `${py + 14}px`);
    tip.selectAll("*").remove();
    tip.append("strong").text(d.data.label);
    tip.append("div").text(`${fmtMt(d.data.value)} Mt · ${fmtPct(d.data.value / total)}`);
    if (d.data.members) {
      tip.append("div").text(`${d.data.members} small items, see table`);
    }
    if (d.data.drill) {
      tip.append("div").attr("class", "hint").text("Click to see countries");
    }
  }

  function hideTip() {
    tip.attr("hidden", "");
  }

  // ---------- drawing ----------

  function draw(model) {
    const slices = pie(model.slices);

    const paths = arcs
      .selectAll("path")
      .data(slices, (d) => d.data.key)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("fill", (d) => d.data.color)
            .each(function (d) {
              // new slices grow out of a zero-width wedge
              this._current = {
                startAngle: d.startAngle,
                endAngle: d.startAngle,
                padAngle: 0,
              };
            }),
        (update) => update.attr("fill", (d) => d.data.color),
        (exit) => exit.remove()
      );

    paths
      .style("cursor", (d) => (d.data.drill ? "pointer" : "default"))
      .on("click", (event, d) => {
        if (d.data.drill) drillInto(d.data.key);
      })
      .on("mouseenter", function () {
        paths.attr("opacity", 0.55);
        d3.select(this).attr("opacity", 1);
      })
      .on("mousemove", (event, d) => showTip(event, d, model.total))
      .on("mouseleave", () => {
        paths.attr("opacity", 1);
        hideTip();
      })
      .transition()
      .duration(600)
      .attrTween("d", function (d) {
        const to = {
          startAngle: d.startAngle,
          endAngle: d.endAngle,
          padAngle: d.padAngle,
        };
        const interpolate = d3.interpolate(this._current, to);
        this._current = to;
        return (t) => arc(interpolate(t));
      });

    centreTop.text(model.centre[0]);
    centreBottom.text(model.centre[1]);
    svg.attr("aria-label", `${model.title}. Exact values are in the table.`);

    const tbody = d3.select("#shares-table tbody");
    tbody
      .selectAll("tr")
      .data(model.rows, (d) => d.key)
      .join("tr")
      .each(function (d) {
        const tr = d3.select(this).html("");
        const first = tr.append("td");
        first.append("span").attr("class", "swatch").style("background", d.swatch);
        if (d.drill) {
          first
            .append("button")
            .attr("type", "button")
            .attr("class", "linklike")
            .text(d.label)
            .on("click", () => drillInto(d.key));
        } else {
          first.append("span").text(d.label);
        }
        tr.append("td").attr("class", "num").text(fmtMt(d.value));
        tr.append("td").attr("class", "num").text(fmtPct(d.value / model.total));
      })
      .order();
  }

  async function render() {
    const myToken = ++token; // ignore results from superseded renders
    let data;
    try {
      data = await load(state.year);
    } catch (err) {
      if (myToken === token) say(`Could not load data: ${err.message}`, true);
      return;
    }
    if (myToken !== token) return;
    say("");

    if (state.year == null) {
      state.year = data.year;
      slider.max = data.year;
      slider.value = data.year;
      slider.disabled = false;
    }
    yearLabel.textContent = state.year;

    let continent = null;
    if (state.drill) {
      continent = data.continents.find((c) => c.name === state.drill) ?? null;
      if (!continent) state.drill = null; // not present in this year
    }
    backButton.hidden = !state.drill;

    const model = continent ? drillModel(continent, data) : topModel(data);
    d3.select("#shares-title").text(model.title);
    d3.select("#shares-sub").text(model.sub);
    d3.select("#shares-note").text(model.note);
    draw(model);
  }

  // ---------- start-up ----------

  slider.addEventListener("input", () => {
    state.year = Number(slider.value);
    render();
  });
  backButton.addEventListener("click", () => {
    state.drill = null;
    hideTip();
    render();
  });

  render().catch((err) => say(`Could not start: ${err.message}`, true));
})();