plugins {
    kotlin("jvm") version "2.4.10"
    kotlin("plugin.spring") version "2.4.10"
    id("org.springframework.boot") version "4.1.0"
}

springBoot { mainClass.set("dev.kyrion.core.KyrionCoreApplicationKt") }

group = "dev.kyrion"
version = "0.1.0-SNAPSHOT"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(platform("org.springframework.boot:spring-boot-dependencies:4.1.0"))
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.boot:spring-boot-starter-flyway")
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("org.springframework.boot:spring-boot-starter-mail")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
    implementation("org.springframework.security:spring-security-crypto")
    implementation("org.bouncycastle:bcprov-jdk18on:1.84")
    implementation("org.jmdns:jmdns:3.6.3")
    implementation("org.flywaydb:flyway-database-postgresql")
    implementation(kotlin("reflect"))
    implementation("org.apache.pdfbox:pdfbox:3.0.7")
    runtimeOnly("org.postgresql:postgresql")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.boot:spring-boot-starter-webmvc-test")
    testImplementation("org.testcontainers:testcontainers-junit-jupiter")
    testImplementation("org.testcontainers:testcontainers-postgresql")
}

kotlin {
    compilerOptions {
        freeCompilerArgs.add("-Xjsr305=strict")
    }
}

tasks.withType<Test> {
    useJUnitPlatform()
}

val knowledgeParserJar by tasks.registering(Jar::class) {
    archiveFileName.set("knowledge-parser.jar")
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    from(sourceSets.main.get().output) { include("dev/kyrion/core/knowledge/ingestion/PdfParserMain*.class") }
    from(configurations.runtimeClasspath.get().filter {
        it.name.startsWith("pdfbox") || it.name.startsWith("fontbox") || it.name.startsWith("commons-logging")
    }.map { zipTree(it) })
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA")
}
tasks.named("bootJar") { dependsOn(knowledgeParserJar) }
tasks.withType<Test> { dependsOn(knowledgeParserJar) }
