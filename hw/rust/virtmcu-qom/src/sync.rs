#[repr(C, align(8))]
/// A struct
pub struct QemuMutex {
    _opaque: [u8; 64],
}

#[repr(C, align(8))]
/// A struct
pub struct QemuCond {
    _opaque: [u8; 56],
}

extern "C" {
    /// A function
    pub fn virtmcu_bql_locked() -> bool;
    /// A function
    pub fn virtmcu_bql_lock();
    /// A function
    pub fn virtmcu_bql_unlock();
    /// A function
    pub fn virtmcu_bql_force_unlock();
    /// A function
    pub fn virtmcu_bql_force_lock();

    /// A function
    pub fn virtmcu_mutex_new() -> *mut QemuMutex;
    /// A function
    pub fn virtmcu_mutex_free(mutex: *mut QemuMutex);
    /// A function
    pub fn qemu_mutex_init(mutex: *mut QemuMutex);
    /// A function
    pub fn qemu_mutex_destroy(mutex: *mut QemuMutex);
    /// A function
    pub fn virtmcu_mutex_lock(mutex: *mut QemuMutex);
    /// A function
    pub fn virtmcu_mutex_unlock(mutex: *mut QemuMutex);

    /// A function
    pub fn virtmcu_cond_new() -> *mut QemuCond;
    /// A function
    pub fn virtmcu_cond_free(cond: *mut QemuCond);
    /// A function
    pub fn qemu_cond_init(cond: *mut QemuCond);
    /// A function
    pub fn qemu_cond_destroy(cond: *mut QemuCond);
    /// A function
    pub fn virtmcu_cond_wait(cond: *mut QemuCond, mutex: *mut QemuMutex);
    // Returns non-zero (true) on signal/spurious-wakeup, 0 (false) on timeout.
    // Mirrors QEMU's qemu_cond_timedwait which returns `err != ETIMEDOUT`.
    /// A function
    pub fn virtmcu_cond_timedwait(cond: *mut QemuCond, mutex: *mut QemuMutex, ms: u32) -> i32;
    /// A function
    pub fn virtmcu_cond_signal(cond: *mut QemuCond);
    /// A function
    pub fn virtmcu_cond_broadcast(cond: *mut QemuCond);
}

/// A safe wrapper for the Big QEMU Lock (BQL).
pub struct Bql;

impl Bql {
    /// Acquires the BQL and returns a guard. The lock is released when the guard is dropped.
    pub fn lock() -> BqlGuard {
        unsafe { virtmcu_bql_lock() };
        BqlGuard
    }

    /// Explicitly unlocks the BQL. Use this only when you need to block without holding the lock.
    ///
    /// # Safety
    /// The caller must ensure the BQL is currently held.
    pub unsafe fn unlock() {
        virtmcu_bql_unlock();
    }

    /// Temporarily unlocks the BQL and returns a guard that will relock it when dropped.
    /// Uses force helpers to ensure QEMU's internal TLS state is updated
    /// even when called from a DSO.
    pub fn temporary_unlock() -> BqlUnlockGuard {
        unsafe {
            virtmcu_bql_force_unlock();
        }
        BqlUnlockGuard
    }
}

/// A struct
pub struct BqlGuard;

impl Drop for BqlGuard {
    fn drop(&mut self) {
        unsafe { virtmcu_bql_unlock() };
    }
}

/// A struct
pub struct BqlUnlockGuard;

impl Drop for BqlUnlockGuard {
    fn drop(&mut self) {
        unsafe { virtmcu_bql_force_lock() };
    }
}

/// A struct
pub struct QemuMutexGuard<'a> {
    mutex: *mut QemuMutex,
    _marker: core::marker::PhantomData<&'a mut QemuMutex>,
}

impl QemuMutex {
    /// A method
    pub fn lock(&mut self) -> QemuMutexGuard<'_> {
        unsafe { virtmcu_mutex_lock(core::ptr::from_mut(self)) };
        QemuMutexGuard { mutex: core::ptr::from_mut(self), _marker: core::marker::PhantomData }
    }
}

impl Drop for QemuMutexGuard<'_> {
    fn drop(&mut self) {
        unsafe { virtmcu_mutex_unlock(self.mutex) };
    }
}

impl QemuCond {
    /// A method
    pub fn wait(&mut self, mutex: &mut QemuMutex) {
        unsafe { virtmcu_cond_wait(core::ptr::from_mut(self), core::ptr::from_mut(mutex)) };
    }

    /// A method
    pub fn wait_timeout(&mut self, mutex: &mut QemuMutex, ms: u32) -> bool {
        unsafe {
            virtmcu_cond_timedwait(core::ptr::from_mut(self), core::ptr::from_mut(mutex), ms) != 0
        }
    }

    /// A method
    pub fn signal(&mut self) {
        unsafe { virtmcu_cond_signal(core::ptr::from_mut(self)) };
    }

    /// A method
    pub fn broadcast(&mut self) {
        unsafe { virtmcu_cond_broadcast(core::ptr::from_mut(self)) };
    }
}

const _: () = assert!(core::mem::size_of::<QemuMutex>() == 64);
const _: () = assert!(core::mem::size_of::<QemuCond>() == 56);
