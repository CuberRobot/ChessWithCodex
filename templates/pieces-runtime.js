/* 共享棋子渲染器：回放台和单张棋盘都用它，避免各写一份。

   棋组数据 PIECE_SETS 由 tools/import_pieces.py 生成；每套棋子自带留白不一样，
   这里在首次使用时离屏量出整套棋子的包围盒，之后所有棋子按同一比例、同一条基线摆放。 */
function makePieceRenderer(sets, defaultName) {
  const NS = "http://www.w3.org/2000/svg";
  const table = sets || {};
  const names = Object.keys(table);
  const metrics = new Map();
  let current = table[defaultName] ? defaultName : names[0];

  function measure(name) {
    if (metrics.has(name)) return metrics.get(name);
    const def = table[name];
    let viewBox = def ? def.viewBox : "0 0 100 100";
    let probe = null;
    try {
      probe = document.createElementNS(NS, "svg");
      probe.setAttribute("width", "20");
      probe.setAttribute("height", "20");
      probe.style.position = "absolute";
      probe.style.left = "-9999px";
      document.body.appendChild(probe);
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      for (const key in def.pieces) {
        const holder = document.createElementNS(NS, "svg");
        holder.setAttribute("viewBox", def.viewBox);
        holder.setAttribute("width", "20");
        holder.setAttribute("height", "20");
        holder.innerHTML = def.pieces[key];
        probe.appendChild(holder);
        // getBBox 给的是棋子自己在棋组坐标系里的包围盒——正是这里要的
        const box = holder.getBBox();
        if (box && isFinite(box.x) && isFinite(box.y) && box.width > 0 && box.height > 0) {
          minX = Math.min(minX, box.x);
          minY = Math.min(minY, box.y);
          maxX = Math.max(maxX, box.x + box.width);
          maxY = Math.max(maxY, box.y + box.height);
        }
        holder.remove();
      }
      if (isFinite(minX) && maxX > minX && maxY > minY) {
        viewBox = [minX, minY, maxX - minX, maxY - minY].join(" ");
      }
    } catch (err) {
      viewBox = def ? def.viewBox : viewBox;
    } finally {
      if (probe) probe.remove();
    }
    metrics.set(name, viewBox);
    return viewBox;
  }

  function use(name) {
    if (table[name]) current = name;
    return current;
  }

  /** 造一个棋子元素；cell 是棋盘格坐标（一格 = 1 个单位）。 */
  function node(color, kind, cell, size) {
    const def = table[current];
    const box = size || 0.96;
    const element = document.createElementNS(NS, "svg");
    element.setAttribute("x", cell[0] + (1 - box) / 2);
    element.setAttribute("y", cell[1] + (1 - box) / 2);
    element.setAttribute("width", box);
    element.setAttribute("height", box);
    element.setAttribute("overflow", "visible");
    if (def) {
      element.setAttribute("viewBox", measure(current));
      element.innerHTML = def.pieces[color + kind] || "";
    }
    return element;
  }

  return {
    node: node,
    use: use,
    names: names,
    current: function () {
      return current;
    }
  };
}
