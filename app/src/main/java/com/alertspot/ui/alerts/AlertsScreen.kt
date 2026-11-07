package com.alertspot.ui.alerts

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.alertspot.data.model.AlertDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlertsScreen(
    viewModel: AlertsViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Alertas") },
                actions = {
                    IconButton(onClick = { viewModel.fetchAlerts() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (val state = uiState) {
                is AlertsUiState.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                is AlertsUiState.Error -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(state.message, color = MaterialTheme.colorScheme.error)
                        Button(onClick = { viewModel.fetchAlerts() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is AlertsUiState.Success -> {
                    if (state.alerts.isEmpty()) {
                        Text("No hay alertas", modifier = Modifier.align(Alignment.Center))
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            items(state.alerts) { alert ->
                                AlertItem(
                                    alert = alert,
                                    onConfirm = { viewModel.confirmAlert(alert.id) },
                                    onFalseAlarm = { viewModel.falseAlarm(alert.id) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun AlertItem(
    alert: AlertDto,
    onConfirm: () -> Unit,
    onFalseAlarm: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = "Nodo: ${alert.nodeId} (ID: ${alert.id})", style = MaterialTheme.typography.titleMedium)
            Text(text = "Riesgo: ${alert.riskScore}")
            Text(text = "Estado: ${alert.status}")
            Text(text = "Fecha: ${alert.createdAt}")
            if (alert.sourceMode == "DEMO") {
                Text(text = "DEMO", color = MaterialTheme.colorScheme.error)
            }
            if (alert.status == "PENDING") {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(top = 8.dp)
                ) {
                    Button(onClick = onConfirm) {
                        Text("Confirmar")
                    }
                    OutlinedButton(onClick = onFalseAlarm) {
                        Text("Falsa Alarma")
                    }
                }
            } else {
                if (alert.confirmedBy != null) {
                    Text(text = "Atendido por: ${alert.confirmedBy}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}