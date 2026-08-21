import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

const WIDTH = 640;
const HEIGHT = 420;

export default function PlanTree({ data }) {
  const svgRef = useRef();
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!data) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const root = d3.hierarchy(data, (d) => d.children);
    const layout = d3.tree().size([WIDTH - 60, HEIGHT - 60]);
    layout(root);

    const g = svg.append("g").attr("transform", "translate(30, 30)");

    g.selectAll(".link")
      .data(root.links())
      .join("path")
      .attr("class", "link")
      .attr(
        "d",
        d3
          .linkVertical()
          .x((d) => d.x)
          .y((d) => d.y)
      );

    const node = g
      .selectAll(".node")
      .data(root.descendants())
      .join("g")
      .attr("class", (d) => "node" + (d.data.hot ? " hot" : ""))
      .attr("transform", (d) => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer")
      .on("click", (_, d) => setSelected(d.data));

    node
      .append("circle")
      .attr("r", 7)
      .attr("fill", (d) => (d.data.hot ? "#ff4d3d" : "#39ff9c"));

    node
      .append("text")
      .attr("dy", -12)
      .attr("text-anchor", "middle")
      .text((d) => d.data.type);
  }, [data]);

  return (
    <div>
      <svg ref={svgRef} width={WIDTH} height={HEIGHT} />
      {selected && (
        <div className="inspector">
          <div className="inspector-title">{selected.type}</div>
          {selected.relation && (
            <div className="inspector-row">
              <span>relation</span>
              <span>{selected.relation}</span>
            </div>
          )}
          <div className="inspector-row">
            <span>estimated cost</span>
            <span>{selected.cost_estimated}</span>
          </div>
          <div className="inspector-row">
            <span>rows (actual / est)</span>
            <span>{selected.rows_actual} / {selected.rows_estimated}</span>
          </div>
          <div className="inspector-row">
            <span>time (total / own)</span>
            <span>{selected.time_actual_ms?.toFixed(2)}ms / {selected.own_time_ms?.toFixed(2)}ms</span>
          </div>
          <div className="inspector-row">
            <span>buffers (hit / read)</span>
            <span>{selected.shared_hit_blocks} / {selected.shared_read_blocks}</span>
          </div>
          <div className="inspector-row hot">
            <span>hot node</span>
            <span>{selected.hot ? "yes" : "no"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
