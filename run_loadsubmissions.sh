#!/bin/bash

# Function to print usage
usage() {
    echo "Usage: $0 <source_directory> <course_name> <exercise_name> <delay_in_seconds>"
    echo "Example: $0 /path/to/source coursec e1 5"
    exit 1
}

# Check if exactly four arguments were supplied
if [ "$#" -ne 4 ]; then
    usage
fi

# Define the source directory, course name, exercise name, and delay
SRC_DIR=$1
COURSE_NAME=$2
EXERCISE_NAME=$3
DELAY=$4

# Check if the supplied source directory is valid
if [ ! -d "$SRC_DIR" ]; then
    echo "Error: $SRC_DIR is not a directory"
    usage
fi

# Initialize counter
INDEX=1
SHOULD_MOVE_FILES=false

# Check if files are already distributed
for SUBDIR in "$SRC_DIR"/*; do
  if [ -d "$SUBDIR/ex2" ]; then
    SHOULD_MOVE_FILES=false
    break
  else
    SHOULD_MOVE_FILES=true
  fi
done

# Move files if not already distributed
if $SHOULD_MOVE_FILES; then
  echo "Distributing files..."
  for FILE in "$SRC_DIR"/*; do
    if [ -f "$FILE" ]; then
      # Create the index and ex2 directories
      DEST_DIR="$SRC_DIR/$INDEX/ex2"
      mkdir -p "$DEST_DIR"
      
      # Move the file to the destination directory
      mv "$FILE" "$DEST_DIR"
      
      # Increment the counter
      INDEX=$((INDEX + 1))
    fi
  done
  echo "Files have been distributed."
else
  echo "Files are already distributed."
fi

# Execute the custom Python command for each distributed folder with delay
for SUBDIR in "$SRC_DIR"/*; do
  if [ -d "$SUBDIR/ex2" ]; then
    DEST_DIR="$SUBDIR/ex2"
    COMMAND="python manage.py loadsubmissions $COURSE_NAME/$EXERCISE_NAME $DEST_DIR"
    echo "Running command for $DEST_DIR"
    echo "Command: $COMMAND"
    
    # Execute the command
    eval $COMMAND
    
    # Wait for the specified delay before continuing to the next one
    sleep $DELAY
  fi
done

echo "Commands executed successfully for all folders."
