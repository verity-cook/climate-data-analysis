const margin = { top: 20, right: 30, bottom: 40, left: 60 };
const width = 900;
const height = 450;

async function main() {
  const response = await fetch("/emissions/Germany");
  if (!response.ok) throw new Error(`API error ${response.status}`);
  const data = await response.json();

  const svg = d3
    .select("#chart")
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);

  // Scales translate data values into pixel positions
  const x = d3
    .scaleLinear()
    .domain(d3.extent(data, (d) => d.year))
    .range([margin.left, width - margin.right]);

  const y = d3
    .scaleLinear()
    .domain([0, d3.max(data, (d) => d.co2)])
    .nice()
    .range([height - margin.bottom, margin.top]);

  // Axes
  svg
    .append("g")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).tickFormat(d3.format("d")));

  svg
    .append("g")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y));

  svg
    .append("text")
    .attr("x", margin.left)
    .attr("y", 12)
    .attr("font-size", 12)
    .attr("fill", "#666")
    .text("CO₂ emissions (million tonnes)");

  // A line generator turns an array of points into an SVG path
  const line = d3
    .line()
    .defined((d) => d.co2 != null)
    .x((d) => x(d.year))
    .y((d) => y(d.co2));

  svg
    .append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "steelblue")
    .attr("stroke-width", 2)
    .attr("d", line);
}

main().catch((err) => {
  d3.select("#chart")
    .append("p")
    .attr("class", "error")
    .text(`Could not load data: ${err.message}`);
});