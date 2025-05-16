#Imports
import re
import json
import celery
import itertools

from celery.result import AsyncResult
from data.models import Course
from django.db.models.query import QuerySet
from typing import Generator


# Handle asynchronous task
def handle_async_task(task_state: dict, course_key: str) -> dict:
    # Check if the match graph task is already running
    if task_state["task_id"][1] is None:
        # Task is pending, check state and return result if ready
        async_result = AsyncResult(task_state["task_id"][0])
        if async_result.ready():
            # Task is ready, check state and return result
            if async_result.state == "SUCCESS":
                task_state["graph_data"] = async_result.get()
                async_result.forget()

                # Use the graph data to build clusters
                async_task = build_clusters_for(task_state, course_key, delay=True)

                # Save the task ID to the task state
                task_state["task_id"] = [None, async_task.id]

            else:
                # Task failed, reset task state
                task_state["graph_data"] = {}
                task_state["clusters"] = {}
                task_state["ready"] = True
                task_state["task_id"] = None

    # Check if the cluster task is already running
    if task_state["task_id"][0] is None:
        # Task is pending, check state and return result if ready
        async_result = AsyncResult(task_state["task_id"][1])
        if async_result.ready():
            # Task is ready, check state and return result
            if async_result.state == "SUCCESS":
                task_state["clusters"] = async_result.get()
                async_result.forget()
            else:
                # Task failed, reset task state
                task_state["clusters"] = {}

            # Task is done, reset task id
            task_state["ready"] = True
            task_state["task_id"] = None

    return task_state


# Choose which clusters to build
def build_clusters_for(task_state: dict, course_key: str, delay: bool = False) -> dict | str | None:
    # Check which view the task is coming from
    if task_state["origin"] == "clusters":
        # Check if Celery delay is needed
        if delay:
            return build_clusters.delay(task_state, course_key)
        return build_clusters(task_state, course_key)

    if task_state["origin"] == "graph":
        # Check if Celery delay is needed
        if delay:
            return build_graph_clusters.delay(task_state, course_key)
        return build_graph_clusters(task_state, course_key)

    return None


# Build the clusters
@celery.shared_task
def build_clusters(task_state: dict, course_key: str) -> list[dict]:
    # Get the cluster data from the task state
    students = task_state["graph_data"]["edges"]

    # Store the clusters
    clusters = []

    # Loop through the students and add them to the clusters
    for student in students:

        # Check if the student is already in a cluster
        found = False

        # Loop through the clusters and check if the student is already in one
        for cluster in clusters:
            if student["source"] in cluster["students"] or student["target"] in cluster["students"]:

                # Add the student to the cluster
                cluster["students"].add(student["source"])
                cluster["students"].add(student["target"])

                # Add the similarity to the cluster
                for exercise in student["matches_in_exercises"]:
                    cluster["similarity"].append(exercise["max_similarity"])

                found = True
                break

        # If the student is not in a cluster, create a new one
        if not found:
            similarity = []

            # Add the similarity to the cluster
            for exercise in student["matches_in_exercises"]:
                similarity.append(exercise["max_similarity"])

            # Add the new cluster
            clusters.append({
                "students": set([student["source"], student["target"]]),
                "similarity": similarity,
            })

    merged = False

    # Loop through the clusters and merge them if they have common students
    while not merged:
        merged = True

        # Store the clusters to remove
        remove_clusters = []

        # Create pairs of clusters to compare
        for cluster, other_cluster in itertools.combinations(clusters, 2):
            # Check if the clusters are not the same
            if (
                len(cluster["students"].intersection(other_cluster["students"])) > 0
            ):
                # Merge the clusters
                cluster["students"].update(other_cluster["students"])
                cluster["similarity"] += other_cluster["similarity"]
                merged = False

                # Remove the other cluster
                if cluster["students"] != other_cluster["students"] and other_cluster not in remove_clusters:
                    remove_clusters.append(other_cluster)

        # Remove the clusters that were merged
        if not merged:
            for remove_cluster in remove_clusters:
                clusters.remove(remove_cluster)

    # Sort the clusters
    results = sort_clusters(clusters)

    #Save the clusters to the task state
    save_clusters(results, task_state, course_key)

    return results


# Build the clusters for the graph
@celery.shared_task
def build_graph_clusters(task_state: dict, course_key: str) -> list[list]:
    # Get the cluster data from the task state
    students = task_state["graph_data"]["edges"]

    # Store the clusters
    clusters = []

    # Loop through the students and add them to the clusters
    for student in students:

        # Check if the student is already in a cluster
        found = False

        # Loop through the clusters and check if the student is already in one
        for cluster in clusters:
            if student["source"] in cluster or student["target"] in cluster:
                # Add the student to the cluster
                cluster.add(student["source"])
                cluster.add(student["target"])
                found = True
                break

        # If the student is not in a cluster, create a new one
        if not found:
            clusters.append(set([student["source"], student["target"]]))

    merged = False

    # Loop through the clusters and merge them if they have common students
    while not merged:
        merged = True

        # Store the clusters to remove
        remove_clusters = []

        # Create pairs of clusters to compare
        for cluster, other_cluster in itertools.combinations(clusters, 2):
            # Check if the clusters are not the same
            if (
                len(cluster.intersection(other_cluster)) > 0
            ):
                # Merge the clusters
                cluster.update(other_cluster)
                merged = False

                # Remove the other cluster
                if cluster != other_cluster and other_cluster not in remove_clusters:
                    remove_clusters.append(other_cluster)

        # Remove the clusters that were merged
        if not merged:
            for remove_cluster in remove_clusters:
                clusters.remove(remove_cluster)


    # Convert the clusters to a list
    for i, cluster in enumerate(clusters):
        clusters[i] = list(cluster)

    # Save the clusters to the task state
    save_clusters(clusters, task_state, course_key)

    return clusters


# Sort Clusters
def sort_clusters(clusters: list[dict]) -> list[dict]:
    # Sort the students in the clusters
    for cluster in clusters:
        cluster["students"] = sort_alpha_numeric(list(cluster["students"]))
        cluster["similarity"] = sum(cluster["similarity"]) / len(cluster["similarity"])

    # Sort clusters by similarity. If they are equal, sort by the number of students
    clusters = sorted(clusters, key=lambda x: (x["similarity"], len(x["students"])), reverse=True)

    return clusters


# Alpha numeric sorting
def sort_alpha_numeric(lst: list[str]) -> list[str]:
    return sorted(lst, key = sort_key)


# Sort key function
def sort_key(key: str) -> list:
    return [convert_to_number(c) for c in re.split('([0-9]+)', key)]


# Convert text to a number if it is a digit, otherwise leave it as is
def convert_to_number(text: str) -> int | str:
    return int(text) if text.isdigit() else text


# Save the cluster data to the course object
def save_clusters(clusters: list[dict], task_state: dict, course_key: str):
    # Get the course object
    course = Course.objects.filter(key=course_key).first()

    # Create the cluster data
    cluster_data = {
        "clusters": clusters,
        "min_similarity": task_state["min_similarity"],
        "min_matches": task_state["min_matches"],
        "unique_exercises": task_state["unique_exercises"],
        "date_time": task_state["graph_data"]["date_time"],
        "origin": task_state["origin"],
    }

    # Get the course object and save the cluster data
    course.clusters_json = json.dumps(cluster_data)
    course.save()


# Helper function for presenting submissions in chunks of count
def grouped(iterator: QuerySet, count: int) -> Generator:
    # Yield successive n-sized chunks from l.
    for i in range(0, len(iterator), count):
        yield iterator[i: i + count]
