//Variables

// List of exercise names
var exercise_names = [];

// UI
var buttonsControl = {};
var checkboxesControl = {};

// Functions

// Initialize the data
function initializeData() {
  // Get the exercise names from the class
  getExerciseNames();

  // Initialize the datatable
  initializeTable();
}


// Get exercise names from context
function getExerciseNames() {
  $('.exercise_name').each(function() {
    exercise_names.push($(this).text().trim());
  });
}

// Initialize the table
function initializeTable() {
  var emptyString = DataTable.absoluteOrder( {
    value: "", position: 'bottom'
  });

  $('#studentdatatable').DataTable( {
    lengthMenu: [
      [-1, 10, 25, 100],
      ["All", 10, 25, 100]
    ],
    columnDefs: [
      { type: 'natural', targets: [0,1] },
      { type: emptyString, targets: '_all' },
      { className: 'dt-left', targets: '_all' },
    ],
    fixedColumns: {
      start: 1,
    },
    scrollX: true,
    scrollY: '85vh',
    scrollCollapse: true,
  });

  // Add event listeners to the table cells
  $('#studentdatatable td').on('mouseenter', handleMouseEnter);
  $('#studentdatatable td').on('mouseleave', handleMouseLeave);
}


// Handle mouse enter event
function handleMouseEnter() {
  var table = $('#studentdatatable').DataTable();

  // Get the index of the cell
  let colIdx = table.cell(this).index().column;
  let rowIdx = table.cell(this).index().row;

  //Get head of the column
  let colHead = table.column(colIdx).header();

  // Change the header color
  colHead.classList.add('highlight');

  // Get the first cell of the row
  let rowHead = table.rows(rowIdx).nodes()[0].cells[0];

  // Change the header color
  rowHead.classList.add('highlight');

  // Change the background color of the cell
  this.classList.add('highlight');
}


// Handle mouse leave event
function handleMouseLeave() {
  var table = $('#studentdatatable').DataTable();

  // Get the index of the cell
  let colIdx = table.cell(this).index().column;
  let rowIdx = table.cell(this).index().row;

  //Get head of the column
  let colHead = table.column(colIdx).header();

  // Change the header color
  colHead.classList.remove('highlight');

  // Get the first cell of the row
  let rowHead = table.rows(rowIdx).nodes()[0].cells[0];

  // Change the header color
  rowHead.classList.remove('highlight');

  // Change the background color of the cell
  this.classList.remove('highlight');
}


// initialize the UI
function initializeUI() {
  //Buttons
  buttonsControl.showALL = $('#show_all_exercises');
  buttonsControl.hideALL = $('#hide_all_exercises');
  buttonsControl.showALL.click(showAllExercises);
  buttonsControl.hideALL.click(hideAllExercises);

  // Checkboxes

  // Show staff
  checkboxesControl.showStaff = $('#show_staff');
  checkboxesControl.showStaff.change(showStaff);
  if (checkboxesControl.showStaff.is(':checked')) {
    $('.is_staff').show();
  }
  else {
    $('.is_staff').hide();
  }


  // Show exercises
  for (var i = 0; i < exercise_names.length; i++) {
    checkboxesControl[exercise_names[i]] = $('#show_' + exercise_names[i]);
    checkboxesControl[exercise_names[i]].change(showExercise);
    if (checkboxesControl[exercise_names[i]].is(':checked')) {
      $(`.${exercise_names[i]}_column`).show();
    }
    else {
      $(`.${exercise_names[i]}_column`).hide();
    }
  }
}


// Show all exercises
function showAllExercises() {
  // Check all the checkboxes
  exercise_names.forEach(function(exercise) {
    $('#show_' + exercise).prop('checked', true);
    $(`.${exercise}_column`).show();
  });
}


// Hide all exercises
function hideAllExercises() {
  // Uncheck all the checkboxes
  exercise_names.forEach(function(exercise) {
    $('#show_' + exercise).prop('checked', false);
    $(`.${exercise}_column`).hide();
  });
}


// Show staff
function showStaff() {
  if (this.checked) {
    $('.is_staff').show();
  } else {
    $('.is_staff').hide();
  }
}


// Show exercise
function showExercise() {
  var exercise = this.id.split('_')[1];
  if (this.checked) {
    $(`.${exercise}_column`).show();
  } else {
    $(`.${exercise}_column`).hide();
  }
}


$(initializeData);
$(initializeUI);
