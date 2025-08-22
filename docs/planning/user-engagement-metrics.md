# User Engagement Metrics Framework for CarModPicker

## Overview

This document defines the key engagement metrics for CarModPicker, how to track them, and how to present them effectively to investors, partners, and stakeholders.

---

## Core Engagement Metrics

### 1. Active User Definitions

#### **Daily Active Users (DAU)**

- **Definition**: Users who performed any meaningful action in the last 24 hours
- **Actions that count**:
  - Created/edited a build list
  - Added/removed parts from build lists
  - Searched for parts
  - Viewed a build list (own or others')
  - Created/edited a car profile
  - Logged in and spent >30 seconds on site

#### **Weekly Active Users (WAU)**

- **Definition**: Users who performed meaningful actions in the last 7 days
- **Same actions as DAU, but over 7-day window**

#### **Monthly Active Users (MAU)**

- **Definition**: Users who performed meaningful actions in the last 30 days
- **Industry standard for SaaS/consumer apps**

### 2. Engagement Levels

#### **Power Users (High Engagement)**

- **Criteria**: 5+ build lists, 20+ parts added, 10+ sessions per month
- **Actions**: Creates content, shares build lists, rates parts
- **Value**: Content creators, community leaders

#### **Regular Users (Medium Engagement)**

- **Criteria**: 2-4 build lists, 5-19 parts added, 3-9 sessions per month
- **Actions**: Maintains build lists, occasionally adds parts
- **Value**: Core user base, potential premium subscribers

#### **Casual Users (Low Engagement)**

- **Criteria**: 1 build list, 1-4 parts added, 1-2 sessions per month
- **Actions**: Creates initial build list, minimal activity
- **Value**: Growth potential, viral sharing

---

## Key Performance Indicators (KPIs)

### 1. User Acquisition & Retention

#### **Retention Rates**

```sql
-- Day 1 Retention
SELECT
    COUNT(DISTINCT CASE WHEN days_since_signup >= 1 THEN user_id END) * 100.0 /
    COUNT(DISTINCT user_id) as day_1_retention
FROM user_activity
WHERE signup_date >= CURRENT_DATE - INTERVAL '30 days';

-- Day 7 Retention
SELECT
    COUNT(DISTINCT CASE WHEN days_since_signup >= 7 THEN user_id END) * 100.0 /
    COUNT(DISTINCT user_id) as day_7_retention
FROM user_activity
WHERE signup_date >= CURRENT_DATE - INTERVAL '30 days';

-- Day 30 Retention
SELECT
    COUNT(DISTINCT CASE WHEN days_since_signup >= 30 THEN user_id END) * 100.0 /
    COUNT(DISTINCT user_id) as day_30_retention
FROM user_activity
WHERE signup_date >= CURRENT_DATE - INTERVAL '60 days';
```

#### **Churn Rate**

```sql
-- Monthly Churn Rate
SELECT
    COUNT(DISTINCT churned_users.user_id) * 100.0 /
    COUNT(DISTINCT all_users.user_id) as monthly_churn_rate
FROM (
    SELECT user_id FROM users
    WHERE last_activity_date < CURRENT_DATE - INTERVAL '30 days'
) churned_users
CROSS JOIN (
    SELECT user_id FROM users
    WHERE created_at < CURRENT_DATE - INTERVAL '30 days'
) all_users;
```

### 2. Content Creation & Consumption

#### **Build List Metrics**

```sql
-- Build Lists per User
SELECT
    AVG(build_lists_per_user) as avg_build_lists_per_user,
    MEDIAN(build_lists_per_user) as median_build_lists_per_user,
    COUNT(CASE WHEN build_lists_per_user >= 5 THEN 1 END) as power_users
FROM (
    SELECT user_id, COUNT(*) as build_lists_per_user
    FROM build_lists
    GROUP BY user_id
) user_build_lists;

-- Build List Completion Rate
SELECT
    COUNT(CASE WHEN parts_count > 0 THEN 1 END) * 100.0 /
    COUNT(*) as build_lists_with_parts_rate
FROM (
    SELECT bl.id, COUNT(blp.part_id) as parts_count
    FROM build_lists bl
    LEFT JOIN build_list_parts blp ON bl.id = blp.build_list_id
    GROUP BY bl.id
) build_list_stats;
```

#### **Part Engagement**

```sql
-- Parts per Build List
SELECT
    AVG(parts_per_build_list) as avg_parts_per_build_list,
    MEDIAN(parts_per_build_list) as median_parts_per_build_list
FROM (
    SELECT build_list_id, COUNT(*) as parts_per_build_list
    FROM build_list_parts
    GROUP BY build_list_id
) build_list_parts_count;

-- Part Creation vs. Usage
SELECT
    COUNT(DISTINCT creator_id) as unique_part_creators,
    COUNT(DISTINCT user_id) as unique_part_users,
    COUNT(*) as total_part_uses
FROM parts p
JOIN build_list_parts blp ON p.id = blp.part_id;
```

### 3. Session & Time Metrics

#### **Session Duration**

```sql
-- Average Session Duration
SELECT
    AVG(session_duration_seconds) as avg_session_duration,
    MEDIAN(session_duration_seconds) as median_session_duration
FROM user_sessions
WHERE session_date >= CURRENT_DATE - INTERVAL '30 days';

-- Sessions per User
SELECT
    AVG(sessions_per_user) as avg_sessions_per_user,
    COUNT(CASE WHEN sessions_per_user >= 10 THEN 1 END) as frequent_users
FROM (
    SELECT user_id, COUNT(*) as sessions_per_user
    FROM user_sessions
    WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
) user_sessions_count;
```

#### **Page Views & Actions**

```sql
-- Page Views per Session
SELECT
    AVG(page_views_per_session) as avg_page_views_per_session,
    SUM(total_page_views) as total_page_views
FROM (
    SELECT session_id, COUNT(*) as page_views_per_session
    FROM page_views
    WHERE view_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY session_id
) session_page_views;

-- Actions per Session
SELECT
    AVG(actions_per_session) as avg_actions_per_session,
    COUNT(CASE WHEN actions_per_session >= 5 THEN 1 END) as engaged_sessions
FROM (
    SELECT session_id, COUNT(*) as actions_per_session
    FROM user_actions
    WHERE action_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY session_id
) session_actions;
```

---

## Engagement Scoring System

### 1. User Engagement Score (0-100)

```python
def calculate_engagement_score(user_id: int, days: int = 30) -> float:
    """
    Calculate user engagement score based on multiple factors
    """
    score = 0

    # Build List Activity (30 points)
    build_lists = get_user_build_lists(user_id, days)
    score += min(len(build_lists) * 3, 30)

    # Part Activity (25 points)
    parts_added = get_parts_added_by_user(user_id, days)
    score += min(parts_added * 0.5, 25)

    # Session Activity (20 points)
    sessions = get_user_sessions(user_id, days)
    score += min(sessions * 2, 20)

    # Content Creation (15 points)
    parts_created = get_parts_created_by_user(user_id, days)
    score += min(parts_created * 3, 15)

    # Social Activity (10 points)
    shares = get_build_list_shares(user_id, days)
    score += min(shares * 2, 10)

    return min(score, 100)
```

### 2. Engagement Tiers

#### **Engaged Users (Score 70-100)**

- **Characteristics**: Power users, content creators
- **Actions**: Creates build lists, adds parts, shares content
- **Value**: High LTV, premium conversion potential

#### **Active Users (Score 30-69)**

- **Characteristics**: Regular users, maintains content
- **Actions**: Uses app regularly, some content creation
- **Value**: Core user base, growth potential

#### **At-Risk Users (Score 10-29)**

- **Characteristics**: Low engagement, infrequent use
- **Actions**: Minimal activity, may churn
- **Value**: Re-engagement opportunities

#### **Inactive Users (Score 0-9)**

- **Characteristics**: Signed up but not engaged
- **Actions**: No meaningful activity
- **Value**: Re-acquisition campaigns

---

## Tracking Implementation

### 1. Database Schema for Metrics

```sql
-- User Activity Tracking
CREATE TABLE user_activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL, -- 'login', 'create_build_list', 'add_part', etc.
    action_data JSONB, -- Additional context
    session_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User Sessions
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(100) UNIQUE,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    page_views INTEGER DEFAULT 0,
    actions_count INTEGER DEFAULT 0
);

-- Page Views
CREATE TABLE page_views (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(100),
    page_path VARCHAR(200),
    view_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    time_on_page_seconds INTEGER
);

-- Build List Analytics
CREATE TABLE build_list_analytics (
    id SERIAL PRIMARY KEY,
    build_list_id INTEGER REFERENCES build_lists(id),
    views_count INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    last_viewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2. API Endpoints for Tracking

```python
# backend/app/api/endpoints/analytics.py
@router.post("/analytics/track")
async def track_user_activity(
    activity_data: UserActivityCreate,
    current_user: User = Depends(get_current_user)
):
    """Track user activity for engagement metrics"""

@router.get("/analytics/engagement/{user_id}")
async def get_user_engagement(
    user_id: int,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get user engagement score and metrics"""

@router.get("/analytics/dashboard")
async def get_engagement_dashboard(
    current_user: User = Depends(get_current_user)
):
    """Get overall engagement metrics for admin dashboard"""
```

---

## Presentation for Investors/Partners

### 1. Executive Summary Metrics

#### **User Growth**

- **MAU Growth**: Month-over-month growth rate
- **User Acquisition**: New users per month
- **Retention**: Day 1, Day 7, Day 30 retention rates

#### **Engagement Quality**

- **DAU/MAU Ratio**: Industry standard for engagement quality
  - Excellent: >20%
  - Good: 10-20%
  - Average: 5-10%
  - Poor: <5%

#### **Content Creation**

- **Build Lists Created**: Total and per user
- **Parts Added**: Total and per build list
- **User-Generated Content**: Percentage of content created by users

### 2. Competitive Benchmarks

#### **Industry Standards**

- **SaaS Apps**: 5-15% DAU/MAU
- **Social Apps**: 20-40% DAU/MAU
- **Gaming Apps**: 30-60% DAU/MAU
- **Productivity Apps**: 10-25% DAU/MAU

#### **Target Metrics for CarModPicker**

- **DAU/MAU**: 15-25% (strong engagement for niche app)
- **Monthly Retention**: 40-60% (good for hobby/enthusiast app)
- **Session Duration**: 5-15 minutes (meaningful engagement)
- **Actions per Session**: 3-8 (active usage)

### 3. Revenue Correlation

#### **Engagement to Revenue**

- **Power Users**: 80% premium conversion potential
- **Active Users**: 20-40% premium conversion potential
- **Casual Users**: 5-10% premium conversion potential

#### **LTV by Engagement Tier**

- **Power Users**: $200-500 LTV
- **Active Users**: $50-150 LTV
- **Casual Users**: $10-30 LTV

---

## Automated Reporting

### 1. Daily Reports

- DAU count and growth
- New user registrations
- Key engagement actions

### 2. Weekly Reports

- WAU trends
- Content creation metrics
- User retention analysis

### 3. Monthly Reports

- MAU and growth trends
- Engagement score distribution
- Revenue correlation analysis
- Competitive benchmarking

### 4. Real-time Dashboard

- Live user count
- Current session activity
- Recent content creation
- System performance metrics

---

## Key Success Metrics for Pitching

### 1. **User Growth**

- Month-over-month user growth rate
- Organic vs. paid acquisition
- Viral coefficient (users brought by existing users)

### 2. **Engagement Quality**

- DAU/MAU ratio
- Session duration and frequency
- Actions per session
- Content creation rate

### 3. **Retention & Stickiness**

- Day 1, 7, 30 retention rates
- Churn rate and reasons
- Re-engagement success rate

### 4. **Content Network Effects**

- User-generated content growth
- Content consumption patterns
- Community engagement metrics

### 5. **Revenue Potential**

- Engagement to revenue correlation
- Premium conversion rates by engagement tier
- Average revenue per user (ARPU) by engagement level

This framework provides comprehensive tracking and presentation of user engagement metrics that will be compelling for investors, partners, and internal decision-making.
