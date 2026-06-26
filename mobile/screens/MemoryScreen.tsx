import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, TextInput, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { ApiService } from '../services/api';
import { ScreenContainer } from '../components/ScreenContainer';
import { GlassCard } from '../components/GlassCard';
import { GlowingButton } from '../components/GlowingButton';
import { COLORS } from '../theme/colors';

type TabType = 'context' | 'mind' | 'people';

export const MemoryScreen = () => {
  const [activeTab, setActiveTab] = useState<TabType>('context');
  const [loading, setLoading] = useState<boolean>(false);

  // Layer 1 & 2 State
  const [context, setContext] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);

  // Layer 3 (Mind) State
  const [namespace, setNamespace] = useState<string>('house');
  const [mindQuery, setMindQuery] = useState<string>('');
  const [mindRecords, setMindRecords] = useState<any[]>([]);

  // Layer 4 (Personality) State
  const [peopleQuery, setPeopleQuery] = useState<string>('');
  const [people, setPeople] = useState<any[]>([]);

  // Fetch Context and History on mount / refresh
  const loadContextAndHistory = async () => {
    setLoading(true);
    try {
      const contextData = await ApiService.getMemoryContext();
      setContext(contextData.messages || []);
      
      const historyData = await ApiService.getMemoryHistory(10);
      setHistory(historyData.conversations || []);
    } catch (err) {
      console.error('Failed to load memory context/history', err);
    } finally {
      setLoading(false);
    }
  };

  // Search Mind DB
  const searchMind = async () => {
    if (!namespace.trim()) return;
    setLoading(true);
    try {
      const res = await ApiService.getMemoryMind(namespace, mindQuery || undefined);
      setMindRecords(res.records || []);
    } catch (err) {
      console.error('Failed to search mind', err);
    } finally {
      setLoading(false);
    }
  };

  // Search Personality
  const searchPeople = async () => {
    setLoading(true);
    try {
      const res = await ApiService.getMemoryPersonality(peopleQuery || undefined);
      setPeople(res.people || []);
    } catch (err) {
      console.error('Failed to search personality', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'context') {
      loadContextAndHistory();
    } else if (activeTab === 'mind') {
      searchMind();
    } else if (activeTab === 'people') {
      searchPeople();
    }
  }, [activeTab]);

  return (
    <ScreenContainer>
      <View style={styles.tabContainer}>
        {(['context', 'mind', 'people'] as TabType[]).map((tab) => (
          <TouchableOpacity
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={[
              styles.tabButton,
              activeTab === tab && styles.tabButtonActive,
            ]}
          >
            <Text style={[
              styles.tabText,
              activeTab === tab ? styles.tabTextActive : styles.tabTextInactive,
            ]}>
              {tab.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading && (
        <ActivityIndicator color={COLORS.primary} style={styles.loader} />
      )}

      {!loading && activeTab === 'context' && (
        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Active Context */}
          <GlassCard title="Active Session Context">
            {context.length === 0 ? (
              <Text style={styles.emptyText}>No active conversation context.</Text>
            ) : (
              context.map((msg, index) => (
                <View
                  key={index}
                  style={[
                    styles.chatBubble,
                    msg.role === 'user' ? styles.userBubble : styles.assistantBubble,
                  ]}
                >
                  <Text style={styles.bubbleRole}>
                    {msg.role === 'user' ? 'OPERATOR' : 'RENINE'}
                  </Text>
                  <Text style={styles.bubbleText}>{msg.content}</Text>
                </View>
              ))
            )}
          </GlassCard>

          {/* Conversation History */}
          <GlassCard title="Recent Logs (Layer 2)">
            {history.length === 0 ? (
              <Text style={styles.emptyText}>No recent conversation history.</Text>
            ) : (
              history.map((conv) => (
                <View key={conv.id} style={styles.historyItem}>
                  <Text style={styles.historyDate}>{conv.date || conv.created_at}</Text>
                  <Text style={styles.historySummary}>{conv.summary}</Text>
                </View>
              ))
            )}
          </GlassCard>
        </ScrollView>
      )}

      {!loading && activeTab === 'mind' && (
        <View style={styles.content}>
          <View style={styles.searchRow}>
            <TextInput
              style={[styles.input, styles.namespaceInput]}
              value={namespace}
              onChangeText={setNamespace}
              placeholder="namespace"
              placeholderTextColor={COLORS.textMuted}
              autoCapitalize="none"
            />
            <TextInput
              style={[styles.input, styles.queryInput]}
              value={mindQuery}
              onChangeText={setMindQuery}
              placeholder="Semantic search query..."
              placeholderTextColor={COLORS.textMuted}
              autoCapitalize="none"
            />
            <TouchableOpacity onPress={searchMind} style={styles.searchButton}>
              <Text style={styles.searchBtnText}>QUERY</Text>
            </TouchableOpacity>
          </View>

          <FlatList
            data={mindRecords}
            keyExtractor={(item) => item.id?.toString() || item.key}
            showsVerticalScrollIndicator={false}
            renderItem={({ item }) => (
              <GlassCard title={item.key}>
                <Text style={styles.recordText}>{item.summary}</Text>
                <View style={styles.metaRow}>
                  <Text style={styles.metaText}>ID: {item.id}</Text>
                  <Text style={styles.metaText}>Updated: {new Date(item.updated_at).toLocaleDateString()}</Text>
                </View>
              </GlassCard>
            )}
            ListEmptyComponent={
              <Text style={styles.emptyText}>No matching mind records found.</Text>
            }
          />
        </View>
      )}

      {!loading && activeTab === 'people' && (
        <View style={styles.content}>
          <View style={styles.searchRow}>
            <TextInput
              style={[styles.input, { flex: 1 }]}
              value={peopleQuery}
              onChangeText={setPeopleQuery}
              placeholder="Search people profiles..."
              placeholderTextColor={COLORS.textMuted}
              autoCapitalize="none"
            />
            <TouchableOpacity onPress={searchPeople} style={styles.searchButton}>
              <Text style={styles.searchBtnText}>QUERY</Text>
            </TouchableOpacity>
          </View>

          <FlatList
            data={people}
            keyExtractor={(item) => item.name}
            showsVerticalScrollIndicator={false}
            renderItem={({ item }) => (
              <GlassCard title={item.name} borderColor={COLORS.secondary}>
                <View style={styles.profileRow}>
                  <Text style={styles.profileLabel}>Relationship:</Text>
                  <Text style={styles.profileVal}>{item.relationship || 'Unknown'}</Text>
                </View>
                <View style={styles.profileRow}>
                  <Text style={styles.profileLabel}>Age:</Text>
                  <Text style={styles.profileVal}>{item.age != null ? `${item.age} yrs` : 'N/A'}</Text>
                </View>
                <View style={styles.profileRow}>
                  <Text style={styles.profileLabel}>Birthday:</Text>
                  <Text style={styles.profileVal}>{item.birthday || 'N/A'}</Text>
                </View>
              </GlassCard>
            )}
            ListEmptyComponent={
              <Text style={styles.emptyText}>No matching profiles found.</Text>
            }
          />
        </View>
      )}
    </ScreenContainer>
  );
};

const styles = StyleSheet.create({
  tabContainer: {
    flexDirection: 'row',
    borderBottomWidth: 1.5,
    borderBottomColor: COLORS.cardBorder,
    marginBottom: 20,
  },
  tabButton: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabButtonActive: {
    borderBottomColor: COLORS.primary,
  },
  tabText: {
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1.5,
  },
  tabTextActive: {
    color: COLORS.primary,
  },
  tabTextInactive: {
    color: COLORS.textSecondary,
  },
  content: {
    flex: 1,
  },
  loader: {
    marginTop: 40,
  },
  emptyText: {
    color: COLORS.textMuted,
    textAlign: 'center',
    paddingVertical: 20,
    fontSize: 13,
  },
  chatBubble: {
    padding: 12,
    borderRadius: 8,
    marginVertical: 6,
    borderWidth: 1,
  },
  userBubble: {
    backgroundColor: 'rgba(0, 240, 255, 0.04)',
    borderColor: 'rgba(0, 240, 255, 0.2)',
    alignSelf: 'flex-start',
    width: '90%',
  },
  assistantBubble: {
    backgroundColor: 'rgba(189, 0, 255, 0.04)',
    borderColor: 'rgba(189, 0, 255, 0.2)',
    alignSelf: 'flex-end',
    width: '90%',
  },
  bubbleRole: {
    fontSize: 9,
    fontWeight: 'bold',
    color: COLORS.textSecondary,
    marginBottom: 4,
    letterSpacing: 1,
  },
  bubbleText: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 18,
  },
  historyItem: {
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.cardBorder,
  },
  historyDate: {
    color: COLORS.primary,
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  historySummary: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 18,
  },
  searchRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  input: {
    height: 40,
    backgroundColor: '#0F132A',
    borderColor: COLORS.cardBorder,
    borderWidth: 1,
    borderRadius: 6,
    color: COLORS.text,
    paddingHorizontal: 10,
    fontSize: 13,
  },
  namespaceInput: {
    width: 90,
    marginRight: 6,
  },
  queryInput: {
    flex: 1,
    marginRight: 6,
  },
  searchButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 12,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  searchBtnText: {
    color: COLORS.background,
    fontSize: 11,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  recordText: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 18,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: COLORS.cardBorder,
    paddingTop: 6,
  },
  metaText: {
    color: COLORS.textMuted,
    fontSize: 10,
  },
  profileRow: {
    flexDirection: 'row',
    marginVertical: 4,
  },
  profileLabel: {
    color: COLORS.textSecondary,
    width: 100,
    fontSize: 13,
  },
  profileVal: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: 'bold',
  },
});
