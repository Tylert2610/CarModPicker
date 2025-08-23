# Frontend-Backend Sync Action Plan

## Overview

This document outlines the comprehensive action plan to bring the CarModPicker frontend up to support the current backend state. The backend has implemented several major features that the frontend doesn't currently support, requiring significant updates to the frontend architecture and user interface.

## Current Backend Features vs Frontend Gaps

The backend has implemented several major features that the frontend doesn't support:

1. **Part Inheritance & Global Sharing** - Parts are now globally shared, not tied to build lists
2. **Part Voting System** - Upvote/downvote functionality with vote tracking
3. **Part Reporting System** - Users can report inappropriate parts
4. **Admin Functionality** - Category management, user management, report review
5. **Part Categories** - Categorized parts with filtering and search
6. **Subscription System** - Premium user tiers with limits
7. **Updated Part Schema** - New fields like `category_id`, `brand`, `specifications`, `is_verified`, `source`, `edit_count`

## Phase 1: Core Data Model Updates

### 1.1 Update TypeScript Interfaces

**Priority: Critical**

- Update `frontend/src/types/Api.ts` to match new backend schemas
- Add missing interfaces for categories, subscriptions, votes, reports
- Update Part interfaces to include new fields

### 1.2 Update API Service Layer

**Priority: Critical**

- Update API calls to use new endpoints
- Add new API methods for categories, votes, reports, subscriptions
- Update existing part endpoints to work with global parts

## Phase 2: Part Management Overhaul

### 2.1 Global Parts Catalog

**Priority: High**

- Create new `/parts` page for browsing all parts
- Implement category-based filtering
- Add search functionality
- Display vote counts and user votes
- Show part verification status

### 2.2 Part Detail Page Updates

**Priority: High**

- Update `ViewPart.tsx` to show new fields (category, brand, specifications)
- Add voting UI (upvote/downvote buttons)
- Add report functionality
- Show part creator information
- Display edit history

### 2.3 Part Creation/Editing

**Priority: High**

- Update part forms to include category selection
- Add new fields (brand, part number, specifications)
- Remove build list dependency from part creation

## Phase 3: Build List Integration

### 3.1 Build List - Part Relationship

**Priority: High**

- Update build list pages to show associated parts
- Implement "Add Part to Build List" functionality
- Show parts that can be added to build lists
- Update part removal from build lists

### 3.2 Build List Management

**Priority: Medium**

- Update build list creation/editing
- Show subscription limits for build lists
- Implement part search within build lists

## Phase 4: User Experience Features

### 4.1 Voting System

**Priority: Medium**

- Add vote buttons to part cards and detail pages
- Show vote counts and user's previous votes
- Implement vote removal functionality
- Add visual feedback for voting actions

### 4.2 Reporting System

**Priority: Medium**

- Add report button to part detail pages
- Create report form with reason selection
- Show report status for user's reports
- Implement report history page

### 4.3 Category System

**Priority: Medium**

- Add category filter to parts catalog
- Create category browsing page
- Show category icons and descriptions
- Implement category-based navigation

## Phase 5: Subscription & Admin Features

### 5.1 Subscription Management

**Priority: Low**

- Add subscription status to user profile
- Show current usage vs limits
- Implement upgrade/cancel subscription flows
- Add premium feature indicators

### 5.2 Admin Dashboard

**Priority: Low**

- Create admin-only pages for category management
- Implement user management interface
- Add report review system
- Create admin navigation

## Detailed Implementation Plan

### Step 1: Update TypeScript Types (Week 1)

```typescript
// New interfaces needed in frontend/src/types/Api.ts
export interface Category {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  icon?: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PartVote {
  id: number;
  user_id: number;
  part_id: number;
  vote_type: "upvote" | "downvote";
  created_at: string;
}

export interface PartReport {
  id: number;
  user_id: number;
  part_id: number;
  reason: string;
  description?: string;
  status: "pending" | "resolved" | "dismissed";
  created_at: string;
}

export interface SubscriptionStatus {
  tier: "free" | "premium";
  status: "active" | "cancelled" | "expired";
  expires_at?: string;
  limits: {
    cars: number;
    build_lists: number;
  };
  usage: {
    cars: number;
    build_lists: number;
  };
}

// Updated Part interface
export interface PartRead {
  id: number;
  name: string;
  description?: string;
  price?: number;
  image_url?: string;
  category_id: number;
  user_id: number;
  brand?: string;
  part_number?: string;
  specifications?: Record<string, any>;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface PartReadWithVotes extends PartRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: "upvote" | "downvote" | null;
}
```

### Step 2: Create New API Service Methods (Week 1)

```typescript
// New methods needed in frontend/src/services/Api.ts
export const partsApi = {
  // Get all parts with filtering
  getParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) => apiClient.get<PartRead[]>("/parts", { params }),

  // Get parts with vote data
  getPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) => apiClient.get<PartReadWithVotes[]>("/parts/with-votes", { params }),

  // Vote on a part
  voteOnPart: (partId: number, voteType: "upvote" | "downvote") =>
    apiClient.post<PartVote>(`/part-votes/${partId}/vote`, {
      vote_type: voteType,
    }),

  // Remove vote
  removeVote: (partId: number) =>
    apiClient.delete(`/part-votes/${partId}/vote`),

  // Report a part
  reportPart: (partId: number, reason: string, description?: string) =>
    apiClient.post<PartReport>(`/part-reports/${partId}/report`, {
      reason,
      description,
    }),
};

export const categoriesApi = {
  getCategories: () => apiClient.get<Category[]>("/categories"),
  getCategory: (id: number) => apiClient.get<Category>(`/categories/${id}`),
  getPartsByCategory: (
    categoryId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<PartRead[]>(`/categories/${categoryId}/parts`, { params }),
};

export const subscriptionsApi = {
  getStatus: () => apiClient.get<SubscriptionStatus>("/subscriptions/status"),
  upgrade: (tier: "premium") =>
    apiClient.post("/subscriptions/upgrade", { tier }),
  cancel: () => apiClient.post("/subscriptions/cancel"),
};
```

### Step 3: Create New Pages (Week 2-3)

#### 3.1 Parts Catalog Page (`/parts`)

- Grid layout of all parts
- Category filter sidebar
- Search functionality
- Pagination
- Vote display
- Part cards with voting buttons

#### 3.2 Category Browser Page (`/categories`)

- List all categories
- Category detail pages
- Parts by category
- Category icons and descriptions

#### 3.3 Admin Pages (if user is admin)

- Category management
- Report review
- User management
- Admin dashboard

### Step 4: Update Existing Components (Week 3-4)

#### 4.1 Update PartList Component

- Remove build list dependency
- Add voting functionality
- Show category information
- Add report buttons
- Update to work with global parts

#### 4.2 Update ViewPart Page

- Add voting UI
- Show new part fields (category, brand, specifications)
- Add report functionality
- Display creator info
- Show edit history

#### 4.3 Update Build List Pages

- Show associated parts
- Add part search/selection
- Remove part creation (parts are now global)
- Update part management interface

### Step 5: Add New Components (Week 4-5)

#### 5.1 VoteButtons Component

- Upvote/downvote buttons
- Vote count display
- User vote indication
- Vote removal functionality

#### 5.2 CategoryFilter Component

- Category selection
- Active filter display
- Clear filters
- Category icons

#### 5.3 ReportDialog Component

- Report form
- Reason selection
- Description input
- Report submission

#### 5.4 SubscriptionStatus Component

- Current tier display
- Usage limits
- Upgrade prompts
- Subscription management

## Implementation Priority Order

### Week 1: Foundation Updates

- [ ] Update TypeScript interfaces in `frontend/src/types/Api.ts`
- [ ] Add new API service methods
- [ ] Update existing API calls to work with new endpoints
- [ ] Test API integration

### Week 2: Parts Catalog

- [ ] Create new `/parts` page
- [ ] Implement parts grid layout
- [ ] Add category filtering
- [ ] Add search functionality
- [ ] Create VoteButtons component

### Week 3: Part Details & Voting

- [ ] Update ViewPart page with new fields
- [ ] Add voting functionality to part detail pages
- [ ] Add report functionality
- [ ] Update part cards to show votes
- [ ] Create ReportDialog component

### Week 4: Build List Integration

- [ ] Update build list pages to work with global parts
- [ ] Add "Add Part to Build List" functionality
- [ ] Update part management in build lists
- [ ] Add category filter to build list part selection

### Week 5: Admin & Subscription Features

- [ ] Create admin dashboard (if user is admin)
- [ ] Add subscription status display
- [ ] Implement category management (admin)
- [ ] Add report review system (admin)
- [ ] Create subscription management UI

## Testing Strategy

### Unit Tests

- Test new API methods
- Test voting functionality
- Test category filtering
- Test report submission

### Integration Tests

- Test complete voting flow
- Test part reporting workflow
- Test category-based part browsing
- Test build list part management

### E2E Tests

- Test user registration and part browsing
- Test voting and reporting flows
- Test admin functionality
- Test subscription management

## Migration Considerations

### Data Migration

- Existing parts need category assignments
- User vote data needs to be preserved
- Build list associations need to be maintained

### User Experience

- Ensure smooth transition from old to new part system
- Provide clear guidance for new features
- Maintain familiar navigation patterns

### Backward Compatibility

- Handle any remaining old API calls gracefully
- Provide fallbacks for missing data
- Ensure existing user data is preserved

## File Structure Changes

### New Files to Create

```
frontend/src/
├── pages/
│   ├── parts/
│   │   ├── PartsCatalog.tsx
│   │   └── CategoryBrowser.tsx
│   ├── admin/
│   │   ├── AdminDashboard.tsx
│   │   ├── CategoryManagement.tsx
│   │   ├── ReportReview.tsx
│   │   └── UserManagement.tsx
│   └── subscription/
│       └── SubscriptionManagement.tsx
├── components/
│   ├── parts/
│   │   ├── VoteButtons.tsx
│   │   ├── PartCard.tsx
│   │   └── CategoryFilter.tsx
│   ├── admin/
│   │   ├── ReportDialog.tsx
│   │   └── CategoryForm.tsx
│   └── subscription/
│       └── SubscriptionStatus.tsx
└── services/
    ├── partsApi.ts
    ├── categoriesApi.ts
    ├── votesApi.ts
    ├── reportsApi.ts
    └── subscriptionsApi.ts
```

### Files to Update

```
frontend/src/
├── types/Api.ts (major updates)
├── services/Api.ts (add new methods)
├── pages/builder/
│   ├── ViewPart.tsx (add voting, reporting)
│   ├── ViewBuildlist.tsx (update part management)
│   └── Builder.tsx (update navigation)
├── components/parts/
│   ├── PartList.tsx (remove build list dependency)
│   ├── CreatePartForm.tsx (add category selection)
│   └── EditPartForm.tsx (add new fields)
└── App.tsx (add new routes)
```

## Success Metrics

### User Engagement

- Increase in part browsing activity
- Higher user participation in voting
- More build list creation and sharing

### Technical Metrics

- Reduced API errors
- Improved page load times
- Better search and filter performance

### Business Metrics

- Increased user retention
- Higher subscription conversion rates
- More community-generated content

## Risk Mitigation

### Technical Risks

- **API Integration Issues**: Thorough testing of all new endpoints
- **Performance Degradation**: Implement pagination and lazy loading
- **Data Loss**: Comprehensive backup and migration testing

### User Experience Risks

- **Feature Confusion**: Clear onboarding and help documentation
- **Navigation Complexity**: Maintain familiar patterns where possible
- **Mobile Responsiveness**: Test all new features on mobile devices

### Business Risks

- **User Adoption**: Gradual rollout with feature flags
- **Subscription Model**: Clear value proposition and pricing
- **Content Moderation**: Robust reporting and review system

## Conclusion

This action plan provides a structured approach to bringing the frontend up to support all the current backend features while maintaining a good user experience and following the established patterns in the codebase. The phased approach ensures that core functionality is prioritized and that each phase builds upon the previous one.

The implementation should be done incrementally, with thorough testing at each phase to ensure that existing functionality is not broken and that new features work as expected. Regular user feedback should be collected throughout the implementation to ensure that the new features meet user needs and expectations.
