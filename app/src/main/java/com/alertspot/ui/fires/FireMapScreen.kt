package com.alertspot.ui.fires

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.alertspot.ui.component.OsmMapView
import com.alertspot.ui.component.OsmMarker
import org.osmdroid.util.GeoPoint

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FireMapScreen(
    viewModel: FireMapViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mapa de Monitoreo") },
                actions = {
                    IconButton(onClick = { viewModel.fetchPoints() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (val state = uiState) {
                is FireMapUiState.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                is FireMapUiState.Error -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(state.message, color = MaterialTheme.colorScheme.error)
                        Button(onClick = { viewModel.fetchPoints() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is FireMapUiState.Success -> {
                    val mapCenter = if (state.points.isNotEmpty()) {
                        GeoPoint(state.points.first().lat, state.points.first().lon)
                    } else {
                        GeoPoint(-16.39, -61.05) // Chiquitania
                    }

                    val markers = state.points.map { point ->
                        OsmMarker(
                            position = GeoPoint(point.lat, point.lon),
                            title = point.id,
                            snippet = "${point.type} - Riesgo: ${point.riskLevel ?: "N/A"}",
                            tintColor = when (point.riskLevel) {
                                "NORMAL" -> android.graphics.Color.rgb(52, 199, 89) // Green
                                "WARNING" -> android.graphics.Color.rgb(255, 149, 0) // Orange
                                "CRITICAL" -> android.graphics.Color.rgb(255, 59, 48) // Red
                                else -> android.graphics.Color.rgb(142, 142, 147) // Grey
                            }
                        )
                    }

                    OsmMapView(
                        modifier = Modifier.fillMaxSize(),
                        center = mapCenter,
                        zoom = 10.0,
                        markers = markers,
                        gesturesEnabled = true,
                        userLocation = null,
                        animateKey = markers.size
                    )
                }
            }
        }
    }
}