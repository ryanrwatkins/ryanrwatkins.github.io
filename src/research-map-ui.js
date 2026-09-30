import Graph from "graphology";
import Sigma from "sigma";

const graph = new Graph({type: "undirected"});
const canvas = document.querySelector("#research-map-canvas");
const details = document.querySelector("#research-map-details");
const summaryElement = document.querySelector("#research-map-summary");
const searchInput = document.querySelector("#research-map-search");
const topicFilter = document.querySelector("#research-map-topic-filter");
const resetButton = document.querySelector("#research-map-reset");
const baseUrl = new URL("./", import.meta.url);

let renderer;
let graphData;
let selectedNode = null;

function element(tag, properties = {}) {
  const node = document.createElement(tag);
  Object.assign(node, properties);
  return node;
}

function paperNodes() {
  return graphData.nodes.filter((node) => node.type === "Paper");
}

function paperLink(paper) {
  const link = element("a", {href: paper.url, textContent: paper.title, target: "_blank", rel: "noopener"});
  return link;
}

function showPaperDetails(paper) {
  details.replaceChildren();
  details.append(element("h2", {textContent: paper.title}));
  details.append(element("p", {textContent: paper.abstract}));
  const metadata = element("p", {className: "research-map-meta"});
  metadata.textContent = `Topic: ${paper.topic_label} | Map connections: ${paper.degree}`;
  details.append(metadata, paperLink(paper));

  const related = graph.neighbors(paper.id)
    .map((id) => graphData.nodes.find((node) => node.id === id))
    .filter((node) => node && node.type === "Paper")
    .sort((left, right) => right.degree - left.degree)
    .slice(0, 6);
  if (related.length) {
    details.append(element("h3", {textContent: "Related papers"}));
    const list = element("ul");
    related.forEach((relatedPaper) => {
      const item = element("li");
      item.append(paperLink(relatedPaper));
      list.append(item);
    });
    details.append(list);
  }
}

function showTopicDetails(topic) {
  details.replaceChildren();
  details.append(element("h2", {textContent: topic.label}));
  details.append(element("p", {textContent: `${topic.paper_count} papers | Keywords: ${topic.keywords.join(", ")}`}));
  const list = element("ul");
  topic.paper_ids.slice(0, 15).forEach((id) => {
    const paper = graphData.nodes.find((node) => node.id === id);
    if (paper) {
      const item = element("li");
      const button = element("button", {type: "button", textContent: paper.title});
      button.addEventListener("click", () => selectNode(paper.id));
      item.append(button);
      list.append(item);
    }
  });
  details.append(list);
}

function selectNode(nodeId) {
  selectedNode = nodeId;
  const node = graphData.nodes.find((item) => item.id === nodeId);
  if (!node) return;
  if (node.type === "Paper") showPaperDetails(node);
  else showTopicDetails(node);

  // Sigma normalizes graph coordinates for its camera. Reuse its display
  // coordinates and retain the user's zoom instead of imposing a fixed ratio.
  const displayNode = renderer.getNodeDisplayData(nodeId);
  if (!displayNode) return;
  const camera = renderer.getCamera();
  camera.animate(
    {x: displayNode.x, y: displayNode.y, ratio: camera.getState().ratio},
    {duration: 280},
  );
}

function applyFilters() {
  const query = searchInput.value.trim().toLocaleLowerCase();
  const topic = topicFilter.value;
  graph.forEachNode((id, attributes) => {
    if (attributes.kind === "Topic") {
      graph.setNodeAttribute(id, "hidden", Boolean(topic) && String(attributes.topic_id) !== topic);
      return;
    }
    const matchesQuery = !query || `${attributes.title} ${attributes.topic_label}`.toLocaleLowerCase().includes(query);
    const matchesTopic = !topic || String(attributes.topic_id) === topic;
    graph.setNodeAttribute(id, "hidden", !(matchesQuery && matchesTopic));
  });
  graph.forEachEdge((edge, attributes, source, target) => {
    graph.setEdgeAttribute(edge, "hidden", graph.getNodeAttribute(source, "hidden") || graph.getNodeAttribute(target, "hidden"));
  });
  renderer.refresh();
}

function populateTopics(summary) {
  [...summary.topics]
    .sort((left, right) => right.paper_count - left.paper_count)
    .forEach((topic) => topicFilter.append(element("option", {value: String(topic.id), textContent: `${topic.label} (${topic.paper_count})`})));
}

function renderSummary(summary) {
  summaryElement.textContent = `${summary.paper_count} papers, ${summary.topic_count} topic groups, ${summary.unclustered_paper_count} papers outside a stable cluster, and ${summary.similarity_edge_count} semantic connections.`;
}

async function initialize() {
  try {
    const [graphResponse, summaryResponse] = await Promise.all([
      fetch(new URL("research_graph.json", baseUrl)),
      fetch(new URL("research_summary.json", baseUrl)),
    ]);
    if (!graphResponse.ok || !summaryResponse.ok) throw new Error("The research-map data files could not be loaded.");
    graphData = await graphResponse.json();
    const summary = await summaryResponse.json();
    graphData.nodes.forEach((node) => graph.addNode(node.id, {...node, kind: node.type, type: "circle"}));
    graphData.edges.forEach((edge) => graph.addEdgeWithKey(edge.id, edge.source, edge.target, edge));
    renderer = new Sigma(graph, canvas, {renderEdgeLabels: false, labelDensity: 0.06, labelGridCellSize: 100, defaultEdgeColor: "#d7e0e5"});
    renderer.on("clickNode", ({node}) => selectNode(node));
    renderer.on("enterNode", ({node}) => canvas.setAttribute("aria-label", graph.getNodeAttribute(node, "label")));
    populateTopics(summary);
    renderSummary(summary);
    searchInput.addEventListener("input", applyFilters);
    topicFilter.addEventListener("change", applyFilters);
    resetButton.addEventListener("click", () => {
      searchInput.value = "";
      topicFilter.value = "";
      selectedNode = null;
      details.textContent = "Select a paper or topic to inspect it.";
      applyFilters();
      renderer.getCamera().animatedReset({duration: 300});
    });
  } catch (error) {
    canvas.textContent = error.message;
    console.error(error);
  }
}

initialize();
