package com.alertspot.ui.fires

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.alertspot.data.model.FireOverview
import com.alertspot.ui.theme.*

@Composable
fun FireScreen(
    viewModel: FireViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            @OptIn(ExperimentalMaterial3Api::class)
            TopAppBar(
                title = { Text("SAT Bolivia — Incendios") },
                actions = {
                    IconButton(onClick = { viewModel.fetchOverview() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center
        ) {
            when (val state = uiState) {
                is FireUiState.Loading -> CircularProgressIndicator()
                is FireUiState.Error -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(state.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.fetchOverview() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is FireUiState.Success -> {
                    FireOverviewContent(state.overview, state.healthOk)
                }
            }
        }
    }
}

@Composable
fun FireOverviewContent(overview: FireOverview, healthOk: Boolean) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = when (overview.riskLevel) {
                    "NORMAL" -> BlueLight
                    "WARNING" -> Orange
                    "CRITICAL" -> Red
                    else -> MaterialTheme.colorScheme.surfaceVariant
                }
            )
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "Región: ${overview.region}",
                    style = MaterialTheme.typography.titleLarge
                )
                Text(
                    text = "Riesgo: ${overview.riskScore} (${overview.riskLevel})",
                    style = MaterialTheme.typography.headlineMedium
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Temp: ${overview.temperatureC}°C")
            Text("Humedad: ${overview.humidityPct}%")
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Viento: ${overview.windKmh} km/h")
            Text("Humo: ${overview.smokeIndex}")
        }

        Text("Focos activos: ${overview.activeHotspots}")
        Text("Actualizado: ${overview.updatedAt}")

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (overview.sourceMode == "DEMO") {
                Badge(containerColor = MaterialTheme.colorScheme.tertiary) {
                    Text("MODO DEMO", modifier = Modifier.padding(8.dp))
                }
            }
            if (healthOk) {
                Badge(containerColor = androidx.compose.ui.graphics.Color(0xFF34C759)) {
                    Text("API REAL CONECTADA", modifier = Modifier.padding(8.dp))
                }
            } else {
                Badge(containerColor = MaterialTheme.colorScheme.error) {
                    Text("ERROR API REAL", modifier = Modifier.padding(8.dp))
                }
            }
        }
    }
}