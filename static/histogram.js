JS.prototype.histogram = function(element, values, width, height) {
	this.log("Generating histogram.");
	var js = this;
	var w = width - 20;
	var h = height - 20;
	
	// Scales.
	var x = d3.scale.linear().domain([ 0, 1 ]).range([ 0, w ]);
	var data = d3.layout.histogram().bins(x.ticks(20))(values);
	var y = d3.scale.linear().domain([ 0, d3.max(data, function(d) { return d.y; }) ]).range([ h, 0 ]);
	
	// Components.
	var svg = d3.select(element[0]).append("svg")
		.attr("width", width)
		.attr("height", height)
		.append("g")
		.attr("transform", "translate(10,0)");
	var bar = svg.selectAll(".bar").data(data).enter()
		.append("g")
		.attr("class", function(d) { return "bar " + js.heat(d.x); })
		.attr("transform", function(d) { return "translate(" + x(d.x) + "," + y(d.y) + ")"; });
	bar.append("rect")
		.attr("x", 1)
		.attr("width", x(data[0].dx) - 1)
		.attr("height", function(d) { return h - y(d.y); });
	
	// Texts.
	var formatCount = d3.format(",.0f");
	bar.append("text")
		.attr("dy", ".75em")
		.attr("y", function(d) { return (h - y(d.y) < 20) ? -16 : 6; })
		.attr("x", x(data[0].dx) / 2)
		.attr("text-anchor", "middle")
		.text(function(d) { return d.y > 0 ? formatCount(d.y) : ""; });

	// Axis.
	var xAxis = d3.svg.axis().scale(x).orient("bottom");
	svg.append("g").attr("class", "x axis").attr("transform", "translate(0," + h + ")").call(xAxis);
}
