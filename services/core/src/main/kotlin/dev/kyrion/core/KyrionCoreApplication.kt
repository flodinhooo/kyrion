package dev.kyrion.core

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication

@SpringBootApplication
class KyrionCoreApplication

fun main(args: Array<String>) {
    runApplication<KyrionCoreApplication>(*args)
}
