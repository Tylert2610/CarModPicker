# CarModPicker MVP Development Plan

## Overview

This plan outlines the development roadmap to transform CarModPicker into a cash-flow neutral MVP with premium features, community-driven parts, and sustainable revenue streams.

## Development Timeline

**Total Duration**: 8 weeks across 7 phases

- **Phase 1**: Database Schema & Backend Foundation (Week 1-2)
- **Phase 2**: Backend API Development (Week 2-3)
- **Phase 3**: Frontend Development (Week 3-4)
- **Phase 4**: Ad Integration (Week 4-5)
- **Phase 5**: Engagement Metrics & Analytics (Week 5-6)
- **Phase 6**: Additional MVP Features (Week 6-7)
- **Phase 7**: Testing & Polish (Week 7-8)

## MVP Goals

1. **Premium tier support** for unlimited cars/build lists
2. **Category table support** with pre-populated categories
3. **Shared parts architecture** - community-maintained parts
4. **Non-intrusive ad integration** for revenue
5. **Comprehensive engagement metrics** for growth tracking
6. **Additional features** for growth and user retention

---

## Phase 1: Database Schema & Backend Foundation (Week 1-2)

### 1.1 Premium User System

**Priority: High**

#### Database Changes:

```sql
-- Add subscription fields to users table
ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free';
ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN subscription_status VARCHAR(20) DEFAULT 'active';
```

#### New Models:

```python
# backend/app/api/models/subscription.py
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    tier: Mapped[str] = mapped_column(nullable=False)  # 'free', 'premium'
    status: Mapped[str] = mapped_column(nullable=False)  # 'active', 'cancelled', 'expired'
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Business Logic:

- **Free tier**: 3 cars, 5 build lists
- **Premium tier**: Unlimited cars, unlimited build lists
- **Premium features**: Advanced search, export, priority support

### 1.2 Category System

**Priority: High**

#### New Category Model:

```python
# backend/app/api/models/category.py
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)  # 'exhaust', 'suspension'
    display_name: Mapped[str] = mapped_column(nullable=False)  # 'Exhaust Systems'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Pre-populated Categories:

```sql
INSERT INTO categories (name, display_name, description, sort_order) VALUES
('exhaust', 'Exhaust Systems', 'Exhaust headers, cat-back systems, mufflers', 1),
('intake', 'Intake Systems', 'Cold air intakes, air filters, throttle bodies', 2),
('suspension', 'Suspension', 'Coilovers, shocks, springs, sway bars', 3),
('wheels', 'Wheels & Tires', 'Wheels, tires, wheel accessories', 4),
('brakes', 'Brake Systems', 'Brake pads, rotors, calipers, brake lines', 5),
('engine', 'Engine Performance', 'Turbochargers, superchargers, engine management', 6),
('exterior', 'Exterior', 'Body kits, spoilers, lighting, mirrors', 7),
('interior', 'Interior', 'Seats, steering wheels, shifters, gauges', 8),
('electrical', 'Electrical', 'Batteries, alternators, wiring, audio', 9),
('maintenance', 'Maintenance', 'Oil, filters, fluids, tools', 10),
('other', 'Other', 'Miscellaneous parts and accessories', 99);
```

### 1.3 Shared Parts Architecture

**Priority: High**

#### Updated Part Model:

```python
# backend/app/api/models/part.py
class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    price: Mapped[Optional[int]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    # New fields
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # Creator
    brand: Mapped[Optional[str]] = mapped_column(nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(nullable=True)
    specifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Quality and moderation
    is_verified: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(default='user_created')  # 'user_created', 'scraped', 'verified'
    edit_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category: Mapped["Category"] = relationship("Category")
    creator: Mapped["User"] = relationship("User")
    build_lists: Mapped[List["BuildListPart"]] = relationship("BuildListPart", back_populates="part")
```

#### Build List - Part Junction Table:

```python
# backend/app/api/models/build_list_part.py
class BuildListPart(Base):
    __tablename__ = "build_list_parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(ForeignKey("build_lists.id"), nullable=False)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="parts")
    part: Mapped["Part"] = relationship("Part", back_populates="build_lists")
    user: Mapped["User"] = relationship("User")
```

#### Updated Build List Model:

```python
# backend/app/api/models/build_list.py
class BuildList(Base):
    __tablename__ = "build_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    car: Mapped["Car"] = relationship("Car", back_populates="build_lists")
    owner: Mapped["User"] = relationship("User")
    parts: Mapped[List["BuildListPart"]] = relationship("BuildListPart", back_populates="build_list")
```

---

## Phase 2: Backend API Development (Week 2-3)

### 2.1 Premium Subscription Endpoints

```python
# backend/app/api/endpoints/subscriptions.py
@router.post("/subscriptions/upgrade")
async def upgrade_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user)
):
    """Upgrade user to premium subscription"""

@router.get("/subscriptions/status")
async def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """Get current subscription status and limits"""

@router.post("/subscriptions/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user)
):
    """Cancel premium subscription"""
```

### 2.2 Category Management Endpoints

```python
# backend/app/api/endpoints/categories.py
@router.get("/categories")
async def get_categories():
    """Get all active categories"""

@router.get("/categories/{category_id}")
async def get_category(category_id: int):
    """Get specific category details"""

@router.get("/categories/{category_id}/parts")
async def get_parts_by_category(
    category_id: int,
    skip: int = 0,
    limit: int = 100
):
    """Get parts by category with pagination"""
```

### 2.3 Enhanced Parts Endpoints

```python
# backend/app/api/endpoints/parts.py
@router.post("/parts")
async def create_part(
    part_data: PartCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new shared part"""

@router.get("/parts")
async def get_parts(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get parts with filtering and search"""

@router.put("/parts/{part_id}")
async def update_part(
    part_id: int,
    part_data: PartUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update part (only creator can update)"""

@router.delete("/parts/{part_id}")
async def delete_part(
    part_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete part (only creator can delete)"""
```

### 2.4 Build List - Part Management

```python
# backend/app/api/endpoints/build_lists.py
@router.post("/build-lists/{build_list_id}/parts/{part_id}")
async def add_part_to_build_list(
    build_list_id: int,
    part_id: int,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Add existing part to build list"""

@router.delete("/build-lists/{build_list_id}/parts/{part_id}")
async def remove_part_from_build_list(
    build_list_id: int,
    part_id: int,
    current_user: User = Depends(get_current_user)
):
    """Remove part from build list"""
```

---

## Phase 3: Frontend Development (Week 3-4)

### 3.1 Premium Subscription UI

**New Components:**

- `SubscriptionCard.tsx` - Display current plan and upgrade options
- `UpgradeModal.tsx` - Premium feature comparison and upgrade flow
- `UsageLimits.tsx` - Show current usage vs limits

**Updated Components:**

- `Header.tsx` - Add subscription status indicator
- `Profile.tsx` - Add subscription management section

### 3.2 Category System UI

**New Components:**

- `CategorySelector.tsx` - Dropdown for selecting part categories
- `CategoryFilter.tsx` - Filter parts by category
- `CategoryIcon.tsx` - Display category icons

**Updated Components:**

- `CreatePartForm.tsx` - Add category selection
- `EditPartForm.tsx` - Add category editing
- `PartList.tsx` - Add category filtering

### 3.3 Shared Parts Architecture

**New Components:**

- `PartSearch.tsx` - Search and browse shared parts
- `AddPartToBuildList.tsx` - Modal for adding parts to build lists
- `PartCreator.tsx` - Form for creating new shared parts

**Updated Components:**

- `BuildListDetail.tsx` - Show parts as removable items
- `PartDetail.tsx` - Show part creator and usage statistics

### 3.4 Enhanced User Experience

**New Features:**

- Part search with category filtering
- Part suggestions based on car compatibility
- Community part ratings and reviews
- Part usage statistics

---

## Phase 4: Ad Integration (Week 4-5)

### 4.1 Ad System Architecture

```python
# backend/app/api/models/ad.py
class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    ad_type: Mapped[str] = mapped_column(nullable=False)  # 'banner', 'sidebar', 'inline'
    placement: Mapped[str] = mapped_column(nullable=False)  # 'home', 'parts', 'build_lists'
    content: Mapped[str] = mapped_column(nullable=False)  # HTML content or ad code
    is_active: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=0)
    start_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

### 4.2 Ad Placement Strategy

**Non-intrusive placements:**

- Sidebar on parts browsing pages
- Footer on build list pages
- Inline ads between part suggestions
- Banner on home page (below hero section)

**Ad Types:**

- Google AdSense (easy integration)
- Direct sponsor ads (higher revenue)
- Affiliate product recommendations

### 4.3 Ad Management Endpoints

```python
# backend/app/api/endpoints/ads.py
@router.get("/ads/{placement}")
async def get_ads_by_placement(placement: str):
    """Get active ads for specific placement"""

@router.post("/ads/click/{ad_id}")
async def track_ad_click(
    ad_id: int,
    current_user: Optional[User] = Depends(get_current_optional_user)
):
    """Track ad click for analytics"""
```

---

## Phase 5: Engagement Metrics & Analytics (Week 5-6)

### 5.1 Engagement Tracking System

**Priority: High**

#### Database Schema for Metrics:

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

#### Engagement Scoring System:

```python
# backend/app/utils/engagement_calculator.py
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

### 5.2 Analytics API Endpoints

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

@router.get("/analytics/retention")
async def get_retention_metrics(
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get Day 1, 7, 30 retention rates"""

@router.get("/analytics/dau-mau")
async def get_dau_mau_ratio(
    current_user: User = Depends(get_current_user)
):
    """Get DAU/MAU ratio and trends"""
```

### 5.3 Analytics Dashboard Components

**New Components:**

- `EngagementDashboard.tsx` - Main analytics dashboard
- `UserEngagementChart.tsx` - DAU/MAU trends
- `RetentionMetrics.tsx` - Retention rate visualization
- `UserActivityHeatmap.tsx` - User activity patterns
- `EngagementScoreCard.tsx` - Individual user engagement scores
- `ContentCreationMetrics.tsx` - Build list and part creation stats

### 5.4 Automated Reporting System

```python
# backend/app/services/reporting_service.py
class ReportingService:
    async def generate_daily_report(self):
        """Generate daily engagement report"""

    async def generate_weekly_report(self):
        """Generate weekly trends report"""

    async def generate_monthly_report(self):
        """Generate comprehensive monthly report"""

    async def send_engagement_alerts(self):
        """Send alerts for significant engagement changes"""
```

### 5.5 Key Metrics Tracking

**Core KPIs to Track:**

- **DAU/MAU Ratio**: Target 15-25%
- **Retention Rates**: Day 1 (60-80%), Day 7 (30-50%), Day 30 (20-40%)
- **Engagement Scores**: Distribution across user tiers
- **Content Creation**: Build lists and parts per user
- **Session Metrics**: Duration, frequency, actions per session

## Phase 6: Additional MVP Features (Week 6-7)

### 6.1 User Engagement Features

**New Components:**

- `PartRating.tsx` - Rate and review parts
- `PartComments.tsx` - Comment on parts
- `UserActivity.tsx` - Show user contributions
- `Leaderboard.tsx` - Top contributors

### 6.2 Growth Features

**New Components:**

- `ShareBuildList.tsx` - Social sharing
- `BuildListTemplates.tsx` - Pre-made build lists
- `PartSuggestions.tsx` - AI-powered part recommendations
- `EmailNewsletter.tsx` - Weekly build highlights

### 6.3 Performance Optimizations

- Database query optimization
- Image optimization and CDN
- Caching strategies
- API response optimization

---

## Phase 7: Testing & Polish (Week 7-8)

### 7.1 Comprehensive Testing

- Unit tests for all new features
- Integration tests for API endpoints
- E2E tests for critical user flows
- Performance testing
- Analytics accuracy testing

### 7.2 User Experience Polish

- Loading states and error handling
- Mobile responsiveness
- Accessibility improvements
- Performance optimization
- Analytics dashboard UX

### 7.3 Documentation

- API documentation updates
- User guides for premium features
- Developer documentation
- Deployment guides
- Analytics documentation

---

## Revenue Projections & Cash Flow Analysis

### Revenue Streams:

1. **Premium Subscriptions**: $5-15/month per user
2. **Ad Revenue**: $2-5 CPM (cost per thousand impressions)
3. **Affiliate Commissions**: 2-8% on parts sales

### Break-even Analysis:

**Monthly Costs (Estimated):**

- Hosting: $50-100
- Database: $20-50
- CDN: $20-40
- Third-party services: $30-50
- **Total**: $120-240/month

**Revenue Targets:**

- 50 premium users at $10/month = $500
- 10,000 ad impressions at $3 CPM = $30
- 20 affiliate sales at $25 average = $500
- **Total**: $1,030/month

**Break-even**: 12-24 premium users or 40,000 ad impressions

---

## Success Metrics

### User Engagement:

- **DAU/MAU Ratio**: Target 15-25%
- **Daily/Monthly Active Users**
- **Build lists created per user**
- **Parts added per build list**
- **User retention rates** (Day 1: 60-80%, Day 7: 30-50%, Day 30: 20-40%)
- **Engagement scores** (Power users: 70-100, Active users: 30-69, Casual users: 10-29)

### Revenue Metrics:

- **Premium conversion rate** (Power users: 80%, Active users: 20-40%, Casual users: 5-10%)
- **Ad click-through rates**
- **Affiliate conversion rates**
- **Monthly recurring revenue**

### Growth Metrics:

- **Organic user acquisition**
- **Social sharing rates**
- **User-generated content volume**
- **Community engagement**
- **Viral coefficient** (users brought by existing users)

### Analytics & Insights:

- **Engagement score distribution** across user tiers
- **Content creation metrics** (build lists and parts per user)
- **Session metrics** (duration, frequency, actions per session)
- **Retention cohort analysis**

---

## Risk Mitigation

### Technical Risks:

- Database performance with shared parts
- Ad integration complexity
- Premium feature implementation

### Business Risks:

- Low premium conversion rates
- Ad revenue below projections
- User adoption challenges

### Mitigation Strategies:

- Start with simple ad integration
- Focus on user experience over monetization
- Iterate based on user feedback
- Maintain flexibility in pricing strategy

---

## Next Steps After MVP

### Phase 7: Advanced Features (Post-MVP)

1. **Advanced Search & Filtering**
2. **Part Compatibility Engine**
3. **Build List Templates**
4. **Community Features**
5. **Mobile App Development**

### Phase 8: Monetization Expansion

1. **Strategic Affiliate Partnerships**
2. **Dropshipping Integration**
3. **Sponsored Content**
4. **Enterprise Features**

This development plan provides a clear roadmap to achieve your MVP goals while maintaining focus on user experience and sustainable growth. The phased approach allows for iterative development and validation at each stage.
