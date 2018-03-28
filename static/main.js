/**
 * Toolbox object for the service.
 *
 */
function JS() {
  this.element = $('#js');
}

JS.prototype.log = function(msg) {
  this.element.append(msg + '\n');
};

JS.prototype.getJSON = function(element, success, fail) {
  var url = element.attr('data-url');
  this.log('Getting JSON from ' + url + '...');
  $.getJSON(url, function(data) {
    if (data.length > 0) {
      success(data);
    } else {
      fail();
    }
  });
};

JS.prototype.parseJSON = function(element) {
  var text = element.text().trim();
  if (text.length > 0) {
    return $.parseJSON(text);
  }

  return [];
};

JS.prototype.buildHeat = function(similarity) {
  var m = similarity.length > 0 ? Math.max(d3.median(similarity), 0.01) : 0.01;
  this.median = m;
  this.log('Similarity median ' + this.median);
  this.heatMap = [1.4, 1.3, 1.2].map(
		function(e) { return e * m; }
	);
  this.log('Heat map ' + this.heatMap);
};

JS.prototype.heat = function(value) {
  var i = 0;
  while (i < this.heatMap.length) {
    if (value >= this.heatMap[i]) {
      break;
    }

    i++;
  }

  return 'heat-' + (i + 1);
};

JS.prototype.applyHeat = function(element) {
  var _this = this;
  element.find('[data-similarity]').each(function(index) {
    var cell = $(this);
    cell.addClass(_this.heat(cell.attr('data-similarity')));
  });
};

JS.prototype.quickReview = function(element) {
  var key = element.find('button').val();
  var a = element.find('a[data-review="' + key + '"]');
  if (a.size() > 0) {
    this.quickReviewShow(element, a);
  }

  var _this = this;
  element.find('a').bind('click', function(event) {
    event.preventDefault();
    var a = $(this);
    var data = {
      csrfmiddlewaretoken: element.find('input[name="csrfmiddlewaretoken"]').val(),
      review: parseInt(a.attr('data-review')),
    };
    $.post(element.attr('action'), data, function(res) {
      if (res.success) {
        _this.log('Review stored.');
        _this.quickReviewShow(a.closest('.btn-group'), a);
      }
    }, 'json');
  });
};

JS.prototype.quickReviewShow = function(element, a) {
  element.find('button').removeClass('btn-default btn-primary btn-success btn-info btn-warning btn-danger')
  .addClass('btn-' + a.attr('data-class')).val(a.attr('data-review')).find('.text').text(a.text());
};

var sigmaObject;

JS.prototype.drawGraph = function(graphData) {
  sigmaObject = new sigma({
    renderer: {
      container: "graph-container",
      type: 'canvas'
    },
    settings: {
      minEdgeSize: 1,
      maxEdgeSize: 10,
      enableEdgeHovering: true,
      defaultEdgeHoverColor: '#222',
      edgeHoverExtremities: true,
      edgeLabelSize: 'proportional',
      edgeLabelSizePowRatio: 1.5,
    }
  });
  sigmaFilter = new sigma.plugins.filter(sigmaObject);

  graphData.nodes.forEach(node => {
    sigmaObject.graph.addNode({
      id: node,
      label: node,
      size: 1,
      color: '#444',
    });
  });
  graphData.edges.forEach((i, edge) => {
    sigmaObject.graph.addEdge({
      id: 'e' + i,
      source: edge.source,
      target: edge.target,
      size: edge.count,
      label: '' + edge.count,
      color: '#ccc',
      hover_color: '#222'
    });
  });

  // $("#similarity-input").change(event => {
  //   similarity = event.target.value;
  //   $("#similarity-value").text(similarity);
  //   updateGraph();
  // });

  shuffleGraphLayout(sigmaObject);

  // TODO highlight edge label on edge hover requires custom renderer?
  /*
  sigmaObject.bind('overEdge', event => {
    console.log("overEdge:", event.data.edge);
    sigmaObject.refresh();
  });
  sigmaObject.bind('outEdge', event => {
    console.log("outEdge:", event.data.edge);
    sigmaObject.refresh();
  });
  */

  return sigmaObject;
};

function shuffleGraphLayout(s) {
  s.graph.nodes().forEach(n => {
    n.x = Math.random() - 0.5;
    n.y = Math.random() - 0.5;
  });
  s.startForceAtlas2({worker: true});
  let timeoutID = window.setTimeout(_ => {
    s.stopForceAtlas2();
    s.refresh();
    window.clearTimeout(timeoutID);
  }, 1000);
};
