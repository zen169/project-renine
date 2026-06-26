import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, Modal, ActivityIndicator, Alert } from 'react-native';
import { ApiService } from '../services/api';
import { ScreenContainer } from '../components/ScreenContainer';
import { GlassCard } from '../components/GlassCard';
import { GlowingButton } from '../components/GlowingButton';
import { COLORS } from '../theme/colors';

export const SmartHomeScreen = () => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [domainFilter, setDomainFilter] = useState<string | undefined>(undefined);

  // Staged pending action for confirmation popup
  const [pendingAction, setPendingAction] = useState<any | null>(null);
  const [confirmLoading, setConfirmLoading] = useState<boolean>(false);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const data = await ApiService.getSmartDevices(domainFilter);
      setDevices(data.devices || []);
    } catch (err: any) {
      console.error(err);
      Alert.alert('Load Error', 'Failed to retrieve smart devices.');
    } finally {
      setLoading(false);
    }
  };

  const handleDevicePress = async (entityId: string, currentState: string) => {
    // Standard toggling logic
    const nextService = currentState === 'on' ? 'turn_off' : 'turn_on';
    
    setLoading(true);
    try {
      const res = await ApiService.createSmartHomeAction(entityId, nextService);
      if (res && res.action) {
        setPendingAction(res.action); // Trigger the confirmation modal overlay
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('Action Blocked', err.message || 'Domain or service call is restricted.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmAction = async () => {
    if (!pendingAction) return;
    setConfirmLoading(true);
    try {
      const res = await ApiService.confirmSmartHomeAction(pendingAction.id);
      if (res.success) {
        Alert.alert('Success', res.message);
        setPendingAction(null);
        fetchDevices(); // Refresh states
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('Execution Error', err.message || 'Action has expired or failed.');
      setPendingAction(null);
    } finally {
      setConfirmLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, [domainFilter]);

  const renderDeviceItem = ({ item }: { item: any }) => {
    const isLightOn = item.state === 'on';
    return (
      <TouchableOpacity
        activeOpacity={0.7}
        onPress={() => handleDevicePress(item.entity_id, item.state)}
      >
        <GlassCard 
          title={item.name} 
          borderColor={isLightOn ? COLORS.success : COLORS.cardBorder}
          style={styles.deviceCard}
        >
          <View style={styles.deviceRow}>
            <View>
              <Text style={styles.entityId}>{item.entity_id}</Text>
              <Text style={styles.domainTag}>{item.domain.toUpperCase()}</Text>
            </View>
            <View style={[
              styles.stateBadge,
              isLightOn ? styles.stateOnBadge : styles.stateOffBadge
            ]}>
              <Text style={[
                styles.stateText,
                isLightOn ? { color: COLORS.success } : { color: COLORS.textMuted }
              ]}>
                {item.state.toUpperCase()}
              </Text>
            </View>
          </View>
        </GlassCard>
      </TouchableOpacity>
    );
  };

  return (
    <ScreenContainer>
      {/* Domain Filters */}
      <View style={styles.filterRow}>
        {['ALL', 'LIGHT', 'SWITCH', 'FAN', 'COVER'].map((d) => {
          const filterVal = d === 'ALL' ? undefined : d.toLowerCase();
          const isActive = domainFilter === filterVal;
          return (
            <TouchableOpacity
              key={d}
              style={[styles.filterBtn, isActive && styles.filterBtnActive]}
              onPress={() => setDomainFilter(filterVal)}
            >
              <Text style={[styles.filterText, isActive ? { color: COLORS.background } : { color: COLORS.textSecondary }]}>
                {d}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {loading && devices.length === 0 ? (
        <ActivityIndicator color={COLORS.primary} style={styles.loader} />
      ) : (
        <FlatList
          data={devices}
          keyExtractor={(item) => item.entity_id}
          renderItem={renderDeviceItem}
          onRefresh={fetchDevices}
          refreshing={loading}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No smart devices discovered in cache.</Text>
          }
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* Confirmation Modal Gate */}
      <Modal
        visible={pendingAction !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setPendingAction(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.warningGlow}>CONFIRMATION REQUIRED</Text>
            <Text style={styles.modalSub}>Pending Secure Smart Home Instruction</Text>

            {pendingAction && (
              <View style={styles.actionDetails}>
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>TARGET DEVICE</Text>
                  <Text style={styles.detailValue}>{pendingAction.entity_id}</Text>
                </View>
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>INSTRUCTION</Text>
                  <Text style={[styles.detailValue, { color: COLORS.primary }]}>
                    {pendingAction.service.replace('_', ' ').toUpperCase()}
                  </Text>
                </View>
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>ACTION ID</Text>
                  <Text style={styles.detailValue}>#{pendingAction.id}</Text>
                </View>
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>EXPIRATION</Text>
                  <Text style={[styles.detailValue, { color: COLORS.warning }]}>5 minutes from creation</Text>
                </View>
              </View>
            )}

            <View style={styles.modalButtons}>
              <GlowingButton
                onPress={() => setPendingAction(null)}
                title="Abort Link"
                variant="danger"
                style={styles.modalBtn}
              />
              <GlowingButton
                onPress={handleConfirmAction}
                title="Execute"
                variant="success"
                loading={confirmLoading}
                style={styles.modalBtn}
              />
            </View>
          </View>
        </View>
      </Modal>
    </ScreenContainer>
  );
};

const styles = StyleSheet.create({
  filterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  filterBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginVertical: 4,
  },
  filterBtnActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  filterText: {
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  loader: {
    marginTop: 40,
  },
  deviceCard: {
    marginBottom: 12,
  },
  deviceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  entityId: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: '600',
  },
  domainTag: {
    color: COLORS.textMuted,
    fontSize: 9,
    fontWeight: 'bold',
    marginTop: 4,
    letterSpacing: 1,
  },
  stateBadge: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1.5,
  },
  stateOnBadge: {
    borderColor: COLORS.success,
    backgroundColor: 'rgba(0, 255, 102, 0.04)',
  },
  stateOffBadge: {
    borderColor: COLORS.cardBorder,
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
  },
  stateText: {
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1.5,
  },
  emptyText: {
    color: COLORS.textMuted,
    textAlign: 'center',
    paddingVertical: 30,
    fontSize: 13,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: COLORS.overlay,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.warning,
    padding: 20,
    alignItems: 'center',
  },
  warningGlow: {
    fontSize: 18,
    fontWeight: '900',
    color: COLORS.warning,
    letterSpacing: 2,
    textShadowColor: COLORS.warning,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 8,
  },
  modalSub: {
    color: COLORS.textSecondary,
    fontSize: 11,
    marginTop: 4,
    marginBottom: 20,
    letterSpacing: 1,
  },
  actionDetails: {
    width: '100%',
    backgroundColor: '#070913',
    borderRadius: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginBottom: 24,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginVertical: 4,
  },
  detailLabel: {
    color: COLORS.textMuted,
    fontSize: 9,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  detailValue: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: 'bold',
  },
  modalButtons: {
    flexDirection: 'row',
    width: '100%',
    justifyContent: 'space-between',
  },
  modalBtn: {
    flex: 0.46,
  },
});
