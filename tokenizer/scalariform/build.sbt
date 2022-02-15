ThisBuild / version := "0.1.0-SNAPSHOT"
ThisBuild / scalaVersion := "2.13.8"

scalacOptions ++= Seq("-deprecation", "-feature")

// Scalariform is the library for parsing Scala code (the student's submissions).
// The Scalariform project was stopped in 2019 and is no longer maintained.
// https://mvnrepository.com/artifact/org.scalariform/scalariform
libraryDependencies += "org.scalariform" %% "scalariform" % "0.2.10"

// sbt-assembly plugin for building a JAR package that contains the dependencies as well.
// But don't include the Scala standard library.
assembly / mainClass := Some("ScalariformTokens")
assemblyPackageScala / assembleArtifact := false

