// Variables
var pdfModal;
var fontSize = 14;
var fontSizeSmall = 8;
var pageOrientation;

// Functions

// Initialize the UI
function initializeUI() {
	var pdfButton = $("#PDF");
  pdfButton.on("click", showModal);

  var downloadButton = $("#download");
  downloadButton.on("click", downloadPDF);

  var resetScaleButton = $("#reset-scale");
  resetScaleButton.on("click", resetScale);

  var resetCutoffButton = $("#reset-x-cutoff");
  resetCutoffButton.on("click", resetXCutoff);

  pdfModal = $("#pdf-modal");

  // Get the next and previous buttons
  var nextButton = $("#next-case > a");
  var previousButton = $("#previous-case > a");

  // Check if the href is -1
  if (nextButton.attr("href") === "-1") {
    // Hide the parent element
    nextButton.parent().hide();
  }

  if (previousButton.attr("href") === "-1") {
    // Hide the parent element
    previousButton.parent().hide();
  }
}


// Initialize the PDF download button
function downloadPDF() {
  // Get form data
  var formData = $("#pdf-form").serializeArray();

  // Form data
	pageOrientation = formData.find(item => item.name === 'orientation').value.charAt(0);
  var scale = formData.find(item => item.name === 'scale').value;
  var xCutoff = formData.find(item => item.name === 'x-cutoff').value;

	// Check if the jsPDF library is loaded
	const { jsPDF } = window.jspdf;
	var doc = new jsPDF(pageOrientation);

	// Get url of the current page
	var url = window.location.href;

	// Create title
	var title = url.split('/');
	title = title[title.length - 2]
	titleFormatted = title.replace('-', ' => ')
	doc.text(titleFormatted, 10, 10);

	// Get the date and time
	var dateTime = new Date();
	var date = dateTime.toLocaleDateString();
	var time = dateTime.toLocaleTimeString();
	doc.text("PDF Created: " + date + " " + time, 10, 20);

	// Get the similarity
	var similarity = $('#similarity').text();
	doc.text(similarity, 10, 30);

	// Set the urls
	doc.textWithLink("Link to Radar comparison page:", 10, 40, {url: url});
  doc.setFontSize(fontSizeSmall);
  doc.textWithLink(url, 10, 45, {url: url});
  doc.setFontSize(fontSize);

  //Get student ids
  var students = title.split('-');

  // Check if submissions come from a provider
	var providerA = $('#a-provider').text();
	if (providerA != undefined) {
    var studentA = students[0] + ": ";
    var gradeA = $('#a-grade').text() + "\t";
    var submissionTimeA = $('#a-submission-time').text();
		doc.textWithLink(studentA + gradeA + submissionTimeA, 10, 55, {url: providerA});
    doc.setFontSize(fontSizeSmall);
    doc.textWithLink(providerA, 10, 60, {url: providerA});
    doc.setFontSize(fontSize);
	}

  // Check if submissions come from a provider
	var providerB = $('#b-provider').text();
	if (providerB != undefined) {
    var studentB = students[1] + ": ";
    var gradeB = $('#b-grade').text() + "\t";
    var submissionTimeB = $('#b-submission-time').text();
    doc.textWithLink(studentB + gradeB + submissionTimeB, 10, 70, {url: providerB});
    doc.setFontSize(fontSizeSmall);
    doc.textWithLink(providerB, 10, 75, {url: providerB});
    doc.setFontSize(fontSize);
	}


	// Get the code blocks
	var pdfjs = document.querySelector('#code-blocks');
	var codeA = document.querySelector('.code-a');
	var codeB = document.querySelector('.code-b');

	// Change code blocks height and width
	codeA.style.height = 'auto';
	codeB.style.height = 'auto';
  codeA.style.maxWidth = xCutoff + '%';
  codeB.style.maxWidth = xCutoff + '%';

  // Grab the html for the code blocks and convert them to canvas
	doc.html(pdfjs, {
		callback: function (doc) {
      // Add the list of other comparisons
			addOtherComparisons(doc);

      // Save the PDF
      doc.save(title + '.pdf');

      // Reset the code blocks height and width
			codeA.style.height = '';
			codeB.style.height = '';
      codeA.style.maxWidth = '50%';
      codeB.style.maxWidth = '50%';
		},

    // PDF options
		x: 5,
		y: 85,
    margin: [10, 0, 10, 0],
		html2canvas: {
			scale: scale,
		}
	});

};


// Add other comparisons to the PDF
function addOtherComparisons(doc) {
	// Create a new page
	doc.addPage();

  // Set font size
  doc.setFontSize(fontSize);

	// Add title
	doc.text($("#other-comparisons").text(), 10, 10);

  //Get all the other comparisons
  var otherComparisons = Array.from($('.grid-item a'));

  // Keep count of the spacing between comparisons
  var count = 0;

  //Loop through each comparison and add it to the PDF
  for (let index = 0; index < otherComparisons.length; index++) {
    // Get the comparison link and text
    const comparison = otherComparisons[index];
    var comparisonText = comparison.innerText.split(' ');
    var textSlice1 = comparisonText.slice(0, 4);
    var textSlice2 = comparisonText.slice(-2);
    comparisonText = textSlice1.concat(textSlice2).join(' ').replace('→', '=>');

    // Add the comparison to the PDF
    doc.textWithLink(comparisonText, 10, 20 + (count * 15), {
      url: comparison.href
    });
    doc.setFontSize(fontSizeSmall);

    // Add the link to the comparison
    doc.textWithLink(comparison.href, 10, 25 + (count * 15), {
      url: comparison.href
    });
    doc.setFontSize(fontSize);

    // Add a line break based on orientation
    if (pageOrientation === 'p') {
      var lineBreak = 270;
    } else {
      var lineBreak = 190;
    }

    // Check if there is a need for a new page
    if (30 + (count * 15) > lineBreak) {
      doc.addPage();
      count = -1; // Reset count for new page
    }

    count++;
  }
}


// Show the modal
function showModal() {
  pdfModal.find("h4.modal-title").text("PDF Parameters");
  // Show modal
  pdfModal.modal("toggle");
}


// Reset the scale of pdf
function resetScale() {
  // Reset the scale to 1
  $("#scale").val(0.145);
}


// Reset the x cutoff of pdf
function resetXCutoff() {
  // Reset the x cutoff to 50
  $("#x-cutoff").val(50);
}


$(initializeUI);
